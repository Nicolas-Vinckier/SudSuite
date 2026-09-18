"""API publique des composants d'archive reutilisables de SudMedia."""

from .compression import (
    compress_tar_xz_python,
    compress_zip_python,
    execute_compression,
    select_backend,
)
from .extraction import execute_extraction, extract_tar_xz_python, extract_zip_python
from .models import CompressionBackendError, ExtractionBackendError, FileEntry, Toolchain
from .paths import (
    archive_base_name,
    detect_archive_format,
    safe_member_path,
    scan_folder,
)
from .progress import Progress, ProgressReader
from .toolchain import describe_backend, detect_toolchain, parse_threads
from .verification import verify_archive

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
