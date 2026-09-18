"""Empreintes binaires et perceptuelles utilisées par Sud Duplicate."""

from __future__ import annotations

from pathlib import Path

from SudCore.files import hash_file


def content_hash(path: str | Path) -> str:
    return hash_file(path, "sha256")


def difference_hash(path: str | Path, hash_size: int = 8) -> int:
    """Calcule un dHash robuste aux changements légers de taille/encodage."""
    try:
        from PIL import Image, ImageOps
    except ImportError as error:
        raise RuntimeError(
            "Pillow est requis pour rechercher les images similaires. "
            "Installez-le avec : pip install Pillow"
        ) from error

    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert("L")
        image = image.resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
        pixel_reader = getattr(image, "get_flattened_data", None)
        pixels = list(pixel_reader() if pixel_reader else image.getdata())

    result = 0
    row_width = hash_size + 1
    for row in range(hash_size):
        offset = row * row_width
        for column in range(hash_size):
            result = (result << 1) | int(
                pixels[offset + column] > pixels[offset + column + 1]
            )
    return result


def hamming_distance(first: int, second: int) -> int:
    return (first ^ second).bit_count()
