"""Façade de compatibilité."""
from SudMedia.utils.archive.extraction import (
    execute_extraction,
    extract_tar_members,
    extract_tar_xz_7zip,
    extract_tar_xz_external_xz,
    extract_tar_xz_python,
    extract_zip_7zip,
    extract_zip_python,
    inspect_zip_for_extraction,
)

__all__ = [
    "execute_extraction",
    "extract_tar_members",
    "extract_tar_xz_7zip",
    "extract_tar_xz_external_xz",
    "extract_tar_xz_python",
    "extract_zip_7zip",
    "extract_zip_python",
    "inspect_zip_for_extraction",
]
