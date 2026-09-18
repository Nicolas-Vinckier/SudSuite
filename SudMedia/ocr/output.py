"""Écriture des résultats OCR, indépendante du moteur utilisé."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from SudCore.files import unique_path

from .models import OCRDocument


def render_document(document: OCRDocument) -> str:
    sections = []
    for page in document.pages:
        sections.append(
            f"--- Page {page.number} ({page.source}) ---\n\n{page.text.strip()}"
        )
    return "\n\n".join(sections).rstrip() + "\n"


def write_document(document: OCRDocument, output_directory: str | Path) -> Path:
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    destination = unique_path(directory / f"{document.source_path.stem}_ocr.txt")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=directory
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(render_document(document))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return destination
