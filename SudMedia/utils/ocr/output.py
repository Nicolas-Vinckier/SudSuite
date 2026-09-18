"""Formatage et écriture des documents texte extraits."""

from __future__ import annotations

from pathlib import Path

from ..filesystem.atomic import atomic_write_text
from ..filesystem.paths import unique_path
from .models import OCRDocument


def render_document(document: OCRDocument) -> str:
    """Rend un document extrait sous forme de chaîne de caractères paginée."""
    sections = []
    for page in document.pages:
        sections.append(
            f"--- Page {page.number} ({page.source}) ---\n\n{page.text.strip()}"
        )
    return "\n\n".join(sections).rstrip() + "\n"


def write_document(document: OCRDocument, output_directory: str | Path) -> Path:
    """Écrit le texte du document extrait de manière atomique."""
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    destination = unique_path(directory / f"{document.source_path.stem}_ocr.txt")
    return atomic_write_text(destination, render_document(document))
