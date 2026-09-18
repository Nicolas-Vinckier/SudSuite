"""Façade de compatibilité."""
from SudMedia.utils.text.backends import OCRBackend, TesseractBackend, find_tesseract

__all__ = ["OCRBackend", "TesseractBackend", "find_tesseract"]
