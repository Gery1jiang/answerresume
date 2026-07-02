"""Tests for FileServiceImpl."""

import os
import tempfile
import pytest
from services.impl.file_service import FileServiceImpl


class TestFileServiceImpl:
    @pytest.fixture
    def file_service(self):
        return FileServiceImpl()

    def test_save_upload_creates_file(self, file_service: FileServiceImpl):
        # Override UPLOAD_DIR to a temp dir for the test
        import services.impl.file_service as fs
        orig = fs.UPLOAD_DIR
        fs.UPLOAD_DIR = tempfile.mkdtemp()
        try:
            result = file_service.save_upload("test-user", "resume.pdf", b"%PDF-1.4 content")
            assert result["file_id"].endswith(".pdf")
            assert result["file_name"] == "resume.pdf"
            assert result["file_size"] == 16

            file_path = os.path.join(fs.UPLOAD_DIR, "test-user", result["file_id"])
            assert os.path.exists(file_path)
            with open(file_path, "rb") as f:
                assert f.read() == b"%PDF-1.4 content"
        finally:
            fs.UPLOAD_DIR = orig

    def test_save_upload_unsupported_format(self, file_service: FileServiceImpl):
        with pytest.raises(ValueError, match="不支持的文件格式"):
            file_service.save_upload("test-user", "file.exe", b"data")

    def test_resolve_file_found(self, file_service: FileServiceImpl):
        import services.impl.file_service as fs
        orig = fs.UPLOAD_DIR
        fs.UPLOAD_DIR = tempfile.mkdtemp()
        try:
            result = file_service.save_upload("test-user", "doc.md", b"# Hello")
            file_path = file_service.resolve_file(result["file_id"], "test-user")
            assert os.path.exists(file_path)
            assert result["file_id"] in file_path
        finally:
            fs.UPLOAD_DIR = orig

    def test_resolve_file_not_found(self, file_service: FileServiceImpl):
        import services.impl.file_service as fs
        orig = fs.UPLOAD_DIR
        fs.UPLOAD_DIR = tempfile.mkdtemp()
        try:
            with pytest.raises(FileNotFoundError):
                file_service.resolve_file("nonexistent.pdf", "test-user")
        finally:
            fs.UPLOAD_DIR = orig

    def test_resolve_file_requires_user_id(self, file_service: FileServiceImpl):
        with pytest.raises(ValueError, match="requires user_id"):
            file_service.resolve_file("some.pdf", "")

    def test_parse_document_raises_when_no_worker_url(self, file_service: FileServiceImpl):
        """When FILE_WORKER_URL is not set, raise RuntimeError."""
        import services.impl.file_service as fs
        orig_url = fs.FILE_WORKER_URL
        fs.FILE_WORKER_URL = ""
        try:
            with pytest.raises(RuntimeError, match="FILE_WORKER_URL not configured"):
                file_service.parse_document("/tmp/nonexistent.txt")
        finally:
            fs.FILE_WORKER_URL = orig_url

    def test_clean_ocr_text_removes_artifacts(self):
        from services.impl.file_service import _clean_ocr_text
        dirty = "Hello <!-- image --> world 展开▼ 微信扫码分享"
        clean = _clean_ocr_text(dirty)
        assert "<!-- image -->" not in clean
        assert "展开" not in clean
        assert "微信扫码" not in clean
        assert "Hello" in clean
        assert "world" in clean

    def test_clean_ocr_text_normalizes_newlines(self):
        from services.impl.file_service import _clean_ocr_text
        text = "Line1\n\n\n\nLine2"
        assert _clean_ocr_text(text) == "Line1\n\nLine2"
