"""Façade de compatibilité pour Sud OCR.

La logique OCR réside désormais dans ``SudMedia.utils.text`` (ou ``SudMedia.utils.ocr``).
"""

from __future__ import annotations

try:
    from ..utils.text import (
        OCR_EXTENSIONS,
        OCRBackend,
        OCRDocument,
        OCRPage,
        OCRResult,
        TesseractBackend,
        extract_document,
        find_tesseract,
        process_documents,
        render_document,
        write_document,
    )
except ImportError:
    from utils.text import (
        OCR_EXTENSIONS,
        OCRBackend,
        OCRDocument,
        OCRPage,
        OCRResult,
        TesseractBackend,
        extract_document,
        find_tesseract,
        process_documents,
        render_document,
        write_document,
    )

__all__ = [
    "OCRDocument",
    "OCRPage",
    "OCRResult",
    "OCR_EXTENSIONS",
    "OCRBackend",
    "TesseractBackend",
    "extract_document",
    "find_tesseract",
    "process_documents",
    "render_document",
    "write_document",
]
