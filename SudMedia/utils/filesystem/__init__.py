"""Module filesystem : chemins, scans et quarantaine, au-dessus de SudCore."""

from SudCore.files import (
    IGNORED_DIRECTORY_NAMES,
    atomic_write_json,
    atomic_write_text,
    clean_input_path,
    collect_files,
    paths_overlap,
    unique_path,
)

from .collector import collect_target_files, find_archive_files
from .paths import (
    archive_base_name,
    detect_archive_format,
    make_staging_folder,
    reserve_output_path,
    resolve_archive_output_path,
    resolve_extraction_paths,
    safe_member_path,
    unique_available_path,
)
from .quarantine import QuarantineResult, quarantine_files
from .scanner import ScannedEntry, remove_output_from_entries, scan_folder, walk_filtered

__all__ = [
    "IGNORED_DIRECTORY_NAMES",
    "QuarantineResult",
    "ScannedEntry",
    "archive_base_name",
    "atomic_write_json",
    "atomic_write_text",
    "clean_input_path",
    "collect_files",
    "collect_target_files",
    "detect_archive_format",
    "find_archive_files",
    "make_staging_folder",
    "paths_overlap",
    "quarantine_files",
    "remove_output_from_entries",
    "reserve_output_path",
    "resolve_archive_output_path",
    "resolve_extraction_paths",
    "safe_member_path",
    "scan_folder",
    "unique_available_path",
    "unique_path",
    "walk_filtered",
]
