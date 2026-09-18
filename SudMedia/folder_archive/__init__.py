"""Façade de compatibilité pour SudMedia.folder_archive.

La logique réside désormais dans ``SudMedia.utils.archive`` et ``SudMedia.utils.filesystem``.
"""

from __future__ import annotations

try:
    from ..utils.archive import (
        CompressionBackendError,
        ExtractionBackendError,
        FileEntry,
        Toolchain,
        compress_tar_xz_python,
        compress_zip_python,
        describe_backend,
        detect_toolchain,
        execute_compression,
        execute_extraction,
        extract_tar_xz_python,
        extract_zip_python,
        parse_threads,
        select_backend,
        verify_archive,
    )
    from ..utils.filesystem.paths import (
        archive_base_name,
        detect_archive_format,
        safe_member_path,
    )
    from ..utils.filesystem.scanner import scan_folder
    from ..utils.progress import Progress, ProgressReader
except ImportError:
    from utils.archive import (
        CompressionBackendError,
        ExtractionBackendError,
        FileEntry,
        Toolchain,
        compress_tar_xz_python,
        compress_zip_python,
        describe_backend,
        detect_toolchain,
        execute_compression,
        execute_extraction,
        extract_tar_xz_python,
        extract_zip_python,
        parse_threads,
        select_backend,
        verify_archive,
    )
    from utils.filesystem.paths import (
        archive_base_name,
        detect_archive_format,
        safe_member_path,
    )
    from utils.filesystem.scanner import scan_folder
    from utils.progress import Progress, ProgressReader

__all__ = [
    "CompressionBackendError",
    "ExtractionBackendError",
    "FileEntry",
    "Progress",
    "ProgressReader",
    "Toolchain",
    "archive_base_name",
    "compress_tar_xz_python",
    "compress_zip_python",
    "describe_backend",
    "detect_archive_format",
    "detect_toolchain",
    "execute_compression",
    "execute_extraction",
    "extract_tar_xz_python",
    "extract_zip_python",
    "parse_threads",
    "safe_member_path",
    "scan_folder",
    "select_backend",
    "verify_archive",
]
