"""Calculs d'empreintes binaires et cryptographiques de fichiers."""

from __future__ import annotations

import os
import zlib

from SudCore.files import hash_file


def content_hash(path: str | os.PathLike[str]) -> str:
    """Raccourci pour l'empreinte SHA256 standard."""
    return hash_file(path, "sha256")


def file_crc32(
    path: str | os.PathLike[str],
    *,
    chunk_size: int = 1024 * 1024,
) -> int:
    """Calcule le CRC32 d'un fichier en flux."""
    crc = 0
    with open(path, "rb") as source:
        while chunk := source.read(chunk_size):
            crc = zlib.crc32(chunk, crc)
    return crc
