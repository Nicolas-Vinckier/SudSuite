"""Moteurs d'exécution OCR (Tesseract, etc.)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Protocol


def find_tesseract(custom_path: str | None = None) -> str | None:
    """Localise l'exécutable Tesseract sur le système ou au chemin spécifié."""
    if custom_path:
        path = Path(custom_path).expanduser()
        return str(path) if path.is_file() else None
    return shutil.which("tesseract")


class OCRBackend(Protocol):
    def recognize(self, image_path: str | Path, language: str = "fra+eng") -> str: ...


class TesseractBackend:
    """Adaptateur minimal vers le moteur Tesseract installé localement."""

    def __init__(self, executable: str | None = None, *, timeout: int = 300):
        self.executable = find_tesseract(executable)
        if self.executable is None:
            raise RuntimeError(
                "Tesseract OCR est introuvable. Installez-le puis ajoutez-le au PATH, "
                "ou utilisez --tesseract CHEMIN."
            )
        self.timeout = timeout

    def recognize(self, image_path: str | Path, language: str = "fra+eng") -> str:
        command = [
            self.executable,
            str(image_path),
            "stdout",
            "-l",
            language,
            "--psm",
            "3",
        ]
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=self.timeout,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or f"code {completed.returncode}"
            raise RuntimeError(f"Échec de Tesseract : {detail}")
        return completed.stdout.strip()
