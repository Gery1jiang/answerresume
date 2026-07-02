"""File parsing worker — standalone microservice for document parsing with Docling."""

import os
import sys
import logging
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException

logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("file_worker")

app = FastAPI(title="File Worker", version="1.0.0")

_converter = None


def _init_docling() -> bool:
    global _converter
    if _converter is not None:
        return True
    try:
        if not os.environ.get("HF_ENDPOINT"):
            os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
        from docling.document_converter import DocumentConverter, FormatOption
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import AcceleratorOptions
        from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
        from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
        opts = PdfPipelineOptions()
        opts.do_table_structure = False
        _converter = DocumentConverter(
            format_options={
                InputFormat.PDF: FormatOption(
                    pipeline_options=opts,
                    backend=PyPdfiumDocumentBackend,
                    pipeline_cls=StandardPdfPipeline,
                )
            }
        )
        logger.info("Docling initialized successfully (table structure disabled)")
        return True
    except Exception as e:
        logger.warning("Docling init failed: %s", e)
        return False


SUPPORTED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif",
    ".pdf", ".docx", ".doc", ".md", ".markdown", ".txt",
    ".pptx", ".xlsx", ".html", ".htm",
}

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif"}


def _parse_with_docling(path: str) -> str:
    try:
        result = _converter.convert(path)
    except Exception as e:
        logger.warning("Docling convert failed (first attempt): %s", e)
        return ""
    text = result.document.export_to_markdown().strip()
    if not text or text == "<!-- image -->":
        text = _extract_ocr_text(result.document)
    if not text or text == "<!-- image -->":
        ext = os.path.splitext(path)[1].lower()
        if ext in _IMAGE_EXTS:
            from PIL import Image
            img = Image.open(path)
            w, h = img.size
            if w < 200 or h < 200:
                scale = max(2, 200 // min(w, h) + 1)
                img = img.resize((w * scale, h * scale), Image.LANCZOS)
                scaled = path + ".scaled" + ext
                img.save(scaled)
                try:
                    try:
                        result = _converter.convert(scaled)
                    except Exception as e:
                        logger.warning("Docling convert failed (scaled): %s", e)
                        return ""
                    text = result.document.export_to_markdown().strip()
                    if not text or text == "<!-- image -->":
                        text = _extract_ocr_text(result.document)
                finally:
                    try:
                        os.unlink(scaled)
                    except Exception:
                        pass
    return text or ""


def _extract_ocr_text(doc: "DoclingDocument") -> str:
    parts = []
    for item in doc.texts:
        t = (item.text or "").strip()
        if t:
            parts.append(t)
    return "\n".join(parts)


@app.get("/health")
async def health():
    return {"status": "ok", "docling_available": _converter is not None}


@app.post("/parse")
async def parse(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "Missing filename")
    _, ext = os.path.splitext(file.filename)
    if ext.lower() not in SUPPORTED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported format: {file.filename}")
    content = await file.read()
    if not content:
        raise HTTPException(400, "Empty file")
    with tempfile.NamedTemporaryFile(suffix=ext.lower() or ".bin", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        if not _init_docling():
            if ext.lower() in {".md", ".markdown", ".txt"}:
                text = content.decode("utf-8", errors="replace")
            else:
                raise HTTPException(503, "Docling unavailable; cannot parse binary format")
        else:
            text = _parse_with_docling(tmp_path)
        return {"text": text, "filename": file.filename}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Parse failed for %s: %s", file.filename, e)
        raise HTTPException(500, f"Parse failed: {e}")
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
