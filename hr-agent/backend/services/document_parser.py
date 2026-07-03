"""
Document parser using Docling (IBM).
Unified parsing for: images, PDF, DOCX, MD, PPTX, XLSX, HTML.
Returns markdown text for LLM consumption.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_HAS_DOCLING = False
_converter = None


def _init_docling():
    global _HAS_DOCLING, _converter
    if _converter is not None:
        return True
    try:
        # Force HF mirror since HuggingFace is blocked from mainland China
        if not os.environ.get("HF_ENDPOINT"):
            os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
        from docling.document_converter import (
            DocumentConverter,
            ImageFormatOption,
            PdfFormatOption,
        )
        pipeline_opts = PdfPipelineOptions(
            do_ocr=True,
            ocr_options=RapidOcrOptions(backend="onnxruntime"),
        )
        _converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_opts),
                InputFormat.IMAGE: ImageFormatOption(pipeline_options=pipeline_opts),
            }
        )
        _HAS_DOCLING = True
        logger.info("Docling initialized successfully")
        return True
    except Exception as e:
        logger.warning(f"Docling init failed: {e}")
        _HAS_DOCLING = False
        return False


SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif",
                        ".pdf", ".docx", ".doc", ".md", ".markdown",
                        ".pptx", ".xlsx", ".html", ".htm"}


def is_supported(filename: str) -> bool:
    _, ext = os.path.splitext(filename)
    return ext.lower() in SUPPORTED_EXTENSIONS


def parse_document(file_path: str) -> Optional[str]:
    """
    Parse a document using Docling and return markdown text.
    Supports: images, PDF, DOCX, MD, PPTX, XLSX, HTML.
    Returns None on failure.
    """
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return None

    if not _init_docling():
        _, ext = os.path.splitext(file_path)
        if ext.lower() in {".md", ".markdown", ".txt"}:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Fallback read failed: {e}")
        return None

    try:
        result = _converter.convert(file_path)
        md = result.document.export_to_markdown()
        return md
    except Exception as e:
        logger.error(f"Docling parse failed for {file_path}: {e}")
        _, ext = os.path.splitext(file_path)
        if ext.lower() in {".md", ".markdown", ".txt"}:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                pass
        return None
