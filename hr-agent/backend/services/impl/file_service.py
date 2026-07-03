import os
import uuid
import re
import logging
import httpx
import tempfile
from services.interfaces import FileService
from config import settings
from services.document_parser import parse_document as local_parse

logger = logging.getLogger(__name__)

FILE_WORKER_URL = os.environ.get("FILE_WORKER_URL", "")


def _parse_via_worker(file_path: str) -> str:
    """Send file to the file-worker microservice for parsing. Raises on failure."""
    if not FILE_WORKER_URL:
        raise RuntimeError("FILE_WORKER_URL not configured")
    with open(file_path, "rb") as f:
        resp = httpx.post(
            f"{FILE_WORKER_URL}/parse",
            files={"file": (os.path.basename(file_path), f, "application/octet-stream")},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["text"]


def _clean_ocr_text(text: str) -> str:
    """Clean OCR output: remove docling parser artifacts, page UI elements, recruiter noise."""
    text = re.sub(r'<!--\s*image\s*-->', '', text)
    text = re.sub(r'\[Pas[a-z]*', '', text)
    text = re.sub(r'展开[▼▽]', '', text)
    text = re.sub(r'微信扫码分享', '', text)
    text = re.sub(r'[△▲]举报', '', text)
    text = re.sub(r'完善(在线)?简历|新增附件简历|昌\s+完善|在线简历', '', text)
    text = re.sub(r'继续沟通|感兴趣', '', text)
    text = re.sub(r'^\s*V\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[\u4e00-\u9fff]{2,6}\n+\s*今日活跃', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n(?:不限|G端产品|ERP产品|AI产品|物联网产品|五险一金|年终奖|全勤奖|零食下午茶)', '', text)
    text = re.sub(r'^(\d+)\.\s+\1\.', r'\1.', text, flags=re.MULTILINE)
    text = re.sub(r'^<!--.*-->$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "uploads")
SUPPORTED_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif",
                 ".pdf", ".docx", ".doc", ".md", ".markdown",
                 ".pptx", ".xlsx", ".html", ".htm"}

TYPE_MAP = {
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".bmp": "image",
    ".tiff": "image", ".tif": "image",
    ".pdf": "pdf", ".docx": "docx", ".doc": "docx",
    ".md": "markdown", ".markdown": "markdown",
    ".pptx": "pptx", ".xlsx": "xlsx",
    ".html": "html", ".htm": "html",
}


class FileServiceImpl(FileService):
    """文件服务实现：用户隔离存储，无全局 fallback 搜索。"""

    def _user_dir(self, user_id: str) -> str:
        dir_path = os.path.join(UPLOAD_DIR, user_id)
        os.makedirs(dir_path, exist_ok=True)
        return dir_path

    def save_upload(self, user_id: str, filename: str, content: bytes) -> dict:
        ext = os.path.splitext(filename)[1].lower()
        if ext not in SUPPORTED_EXT:
            raise ValueError(f"不支持的文件格式: {filename}")
        file_id = f"{uuid.uuid4().hex}{ext}"
        save_path = os.path.join(self._user_dir(user_id), file_id)
        with open(save_path, "wb") as f:
            f.write(content)
        return {
            "file_id": file_id,
            "file_name": filename,
            "file_type": TYPE_MAP.get(ext, "unknown"),
            "file_size": len(content),
        }

    def resolve_file(self, file_ref: str, user_id: str) -> str:
        """只搜索用户自己的目录，无全局 fallback。"""
        if not user_id:
            raise ValueError("resolve_file requires user_id")
        file_path = os.path.join(self._user_dir(user_id), file_ref)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_ref}")
        return file_path

    def parse_document(self, file_path: str) -> str:
        text = ""
        if FILE_WORKER_URL:
            try:
                text = _parse_via_worker(file_path)
            except Exception as e:
                logger.warning("File-worker parse failed (%s), falling back to local parser", e)
        if not text:
            text = local_parse(file_path) or ""
        if not text:
            return ""
        return _clean_ocr_text(text)

    def parse_url(self, url: str) -> str:
        """从 URL 下载文件并解析。"""
        try:
            resp = httpx.get(url, timeout=30, follow_redirects=True)
            resp.raise_for_status()
            suffix = os.path.splitext(url.split("?")[0])[1] or ".png"
            if suffix not in SUPPORTED_EXT:
                # If unknown, infer from content-type
                ct = resp.headers.get("content-type", "")
                if "pdf" in ct:
                    suffix = ".pdf"
                elif "image" in ct:
                    suffix = ".png"
                else:
                    suffix = ".bin"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(resp.content)
                tmp_path = tmp.name
            try:
                return self.parse_document(tmp_path)
            finally:
                os.unlink(tmp_path)
        except Exception as e:
            raise RuntimeError(f"下载文件失败: {e}")
