"""Orchestration d'extraction de texte et OCR pour images et PDF."""

from __future__ import annotations

import tempfile
from collections.abc import Iterable
from pathlib import Path

from ..filesystem.collector import collect_files
from ..image.constants import IMAGE_EXTENSIONS
from .backends import OCRBackend
from .models import OCRDocument, OCRPage, OCRResult
from .output import write_document

OCR_EXTENSIONS = (*IMAGE_EXTENSIONS, ".pdf")


def _extract_image(path: Path, backend: OCRBackend, language: str) -> OCRDocument:
    text = backend.recognize(path, language)
    return OCRDocument(path, (OCRPage(1, text, "ocr"),))


def _extract_pdf(
    path: Path,
    backend: OCRBackend | None,
    language: str,
    minimum_native_characters: int,
    dpi: int,
) -> OCRDocument:
    try:
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz
        except ImportError as error:
            raise RuntimeError(
                "PyMuPDF est requis pour lire les PDF. "
                "Installez-le avec : pip install PyMuPDF"
            ) from error

    pages: list[OCRPage] = []
    zoom = dpi / 72
    with fitz.open(path) as document, tempfile.TemporaryDirectory() as temporary_directory:
        for index, page in enumerate(document, start=1):
            native_text = page.get_text("text").strip()
            if len(native_text) >= minimum_native_characters:
                pages.append(OCRPage(index, native_text, "texte PDF"))
                continue
            if backend is None:
                raise RuntimeError(
                    f"La page {index} nécessite Tesseract car elle ne contient pas de texte exploitable."
                )
            image_path = Path(temporary_directory) / f"page_{index:05d}.png"
            page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False).save(image_path)
            pages.append(OCRPage(index, backend.recognize(image_path, language), "ocr"))
    return OCRDocument(path, tuple(pages))


def extract_document(
    path: str | Path,
    backend: OCRBackend | None,
    *,
    language: str = "fra+eng",
    minimum_native_characters: int = 20,
    dpi: int = 300,
) -> OCRDocument:
    """Extrait un document ; le texte PDF natif est toujours privilégié."""
    source = Path(path)
    if source.suffix.lower() == ".pdf":
        return _extract_pdf(
            source, backend, language, minimum_native_characters, dpi
        )
    if backend is None:
        raise RuntimeError("Un moteur OCR est requis pour traiter une image.")
    return _extract_image(source, backend, language)


def process_documents(
    paths: Iterable[str | Path],
    output_directory: str | Path,
    backend: OCRBackend | None,
    *,
    language: str = "fra+eng",
    minimum_native_characters: int = 20,
    dpi: int = 300,
) -> OCRResult:
    """Traite un lot et isole les erreurs document par document."""
    result = OCRResult()
    for path in collect_files(paths, extensions=OCR_EXTENSIONS):
        try:
            document = extract_document(
                path,
                backend,
                language=language,
                minimum_native_characters=minimum_native_characters,
                dpi=dpi,
            )
            output = write_document(document, output_directory)
        except (OSError, RuntimeError, ValueError) as error:
            result.errors.append(f"{path}: {error}")
            continue
        result.documents.append(document)
        result.outputs.append(output)
    return result
