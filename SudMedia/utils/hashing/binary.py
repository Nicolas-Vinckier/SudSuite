"""Calculs d'empreintes binaires et cryptographiques de fichiers."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path


def hash_file(
    path: str | os.PathLike[str],
    algorithm: str = "sha256",
    *,
    chunk_size: int = 1024 * 1024,
) -> str:
    """Calcule une empreinte en flux sans charger tout le fichier en mémoire."""
    digest = hashlib.new(algorithm)
    with open(path, "rb") as source:
        while chunk := source.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def content_hash(path: str | os.PathLike[str]) -> str:
    """Raccourci pour l'empreinte SHA256 standard."""
    return hash_file(path, "sha256")
