"""Façade de compatibilité pour SudMedia.sudmedia_utils.

Tous les utilitaires ont été réorganisés dans le package ``SudMedia.utils``.
Ce module réexporte l'ensemble des symboles pour assurer une rétrocompatibilité
transparente avec les scripts et tests existants.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Permet l'import direct même si le script est lancé de façon isolée
try:
    from .utils import (
        IGNORED_DIRECTORY_NAMES,
        IMAGE_EXTENSIONS,
        IMAGE_OUTPUT_FORMATS,
        MEDIA_EXTENSIONS,
        RESIZE_METHODS,
        VIDEO_EXTENSIONS,
        ProcessingStats,
        Progress,
        ProgressReader,
        QualityAnalysis,
        SizeAnalysis,
        analyze_quality,
        analyze_size_change,
        clean_input_path,
        collect_target_files,
        configure_console_output,
        configure_pillow,
        format_duration,
        format_size,
        format_size_short,
        get_original_image_quality,
        image_save_options,
        normalize_quality,
        paths_overlap,
        prepare_image_for_format,
        prepare_image_for_quality,
        print_processing_summary,
        print_quality_analysis,
        render_progress,
        reserve_output_path,
        resize_image,
        unique_available_path,
        walk_filtered,
    )
except ImportError:
    # Cas d'un lancement direct où le dossier parent n'est pas dans sys.path
    _parent = Path(__file__).resolve().parent
    if str(_parent) not in sys.path:
        sys.path.insert(0, str(_parent))
    from utils import (
        IGNORED_DIRECTORY_NAMES,
        IMAGE_EXTENSIONS,
        IMAGE_OUTPUT_FORMATS,
        MEDIA_EXTENSIONS,
        RESIZE_METHODS,
        VIDEO_EXTENSIONS,
        ProcessingStats,
        Progress,
        ProgressReader,
        QualityAnalysis,
        SizeAnalysis,
        analyze_quality,
        analyze_size_change,
        clean_input_path,
        collect_target_files,
        configure_console_output,
        configure_pillow,
        format_duration,
        format_size,
        format_size_short,
        get_original_image_quality,
        image_save_options,
        normalize_quality,
        paths_overlap,
        prepare_image_for_format,
        prepare_image_for_quality,
        print_processing_summary,
        print_quality_analysis,
        render_progress,
        reserve_output_path,
        resize_image,
        unique_available_path,
        walk_filtered,
    )

__all__ = [
    "IGNORED_DIRECTORY_NAMES",
    "IMAGE_EXTENSIONS",
    "IMAGE_OUTPUT_FORMATS",
    "MEDIA_EXTENSIONS",
    "ProcessingStats",
    "Progress",
    "ProgressReader",
    "QualityAnalysis",
    "RESIZE_METHODS",
    "SizeAnalysis",
    "VIDEO_EXTENSIONS",
    "analyze_quality",
    "analyze_size_change",
    "clean_input_path",
    "collect_target_files",
    "configure_console_output",
    "configure_pillow",
    "format_duration",
    "format_size",
    "format_size_short",
    "get_original_image_quality",
    "image_save_options",
    "normalize_quality",
    "paths_overlap",
    "prepare_image_for_format",
    "prepare_image_for_quality",
    "print_processing_summary",
    "print_quality_analysis",
    "render_progress",
    "reserve_output_path",
    "resize_image",
    "unique_available_path",
    "walk_filtered",
]
