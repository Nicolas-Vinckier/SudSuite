"""Façade de compatibilité."""
from SudMedia.utils.archive.compression import (
    add_entries_to_tar,
    compress_tar_xz_external_7zip,
    compress_tar_xz_external_xz,
    compress_tar_xz_python,
    compress_zip_7zip,
    compress_zip_python,
    copy_with_progress,
    execute_compression,
    select_backend,
    stream_tar_to_process,
)

__all__ = [
    "add_entries_to_tar",
    "compress_tar_xz_external_7zip",
    "compress_tar_xz_external_xz",
    "compress_tar_xz_python",
    "compress_zip_7zip",
    "compress_zip_python",
    "copy_with_progress",
    "execute_compression",
    "select_backend",
    "stream_tar_to_process",
]
