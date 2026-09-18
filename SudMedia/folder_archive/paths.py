"""Façade de compatibilité."""
from SudMedia.utils.filesystem.paths import (
    archive_base_name,
    detect_archive_format,
    make_staging_folder,
    resolve_archive_output_path,
    resolve_extraction_paths,
    safe_member_path,
)
from SudMedia.utils.filesystem.scanner import (
    FileEntry,
    remove_output_from_entries,
    scan_folder,
)

__all__ = [
    "FileEntry",
    "archive_base_name",
    "detect_archive_format",
    "make_staging_folder",
    "remove_output_from_entries",
    "resolve_archive_output_path",
    "resolve_extraction_paths",
    "safe_member_path",
    "scan_folder",
]
