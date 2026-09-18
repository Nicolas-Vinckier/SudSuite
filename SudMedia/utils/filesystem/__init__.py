"""Module filesystem : manipulation sécurisée et unifiée des fichiers et dossiers."""

from .atomic import atomic_write_json, atomic_write_text
from .collector import collect_files, collect_target_files
from .constants import DEFAULT_IGNORED_DIRECTORIES, EXCLUDE_PATTERNS, IGNORED_DIRECTORY_NAMES
from .paths import (
    archive_base_name,
    clean_input_path,
    detect_archive_format,
    make_staging_folder,
    paths_overlap,
    reserve_output_path,
    resolve_archive_output_path,
    resolve_extraction_paths,
    safe_member_path,
    unique_available_path,
    unique_path,
)
from .quarantine import QuarantineResult, quarantine_files
from .scanner import FileEntry, ScannedEntry, remove_output_from_entries, scan_folder, walk_filtered

__all__ = [
    "DEFAULT_IGNORED_DIRECTORIES",
    "EXCLUDE_PATTERNS",
    "FileEntry",
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
