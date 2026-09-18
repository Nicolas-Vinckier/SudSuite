"""Module text : extraction de texte, intégration Tesseract OCR et traitement de PDF."""

from .backends import OCRBackend, TesseractBackend, find_tesseract
from .engine import OCR_EXTENSIONS, extract_document, process_documents
from .models import OCRDocument, OCRPage, OCRResult
from .output import render_document, write_document

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
