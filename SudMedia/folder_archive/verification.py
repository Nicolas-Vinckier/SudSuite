"""Façade de compatibilité."""
from SudMedia.utils.archive.verification import (
    full_verify_xz,
    full_verify_zip,
    quick_verify_xz,
    quick_verify_zip,
    verify_archive,
)

__all__ = [
    "full_verify_xz",
    "full_verify_zip",
    "quick_verify_xz",
    "quick_verify_zip",
    "verify_archive",
]
