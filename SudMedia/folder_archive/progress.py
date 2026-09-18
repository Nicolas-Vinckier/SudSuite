"""Compatibilite : la progression commune vit dans ``sudmedia_utils``."""

try:
    from ..sudmedia_utils import (
        Progress,
        ProgressReader,
        format_duration,
        format_size_short,
    )
except ImportError:
    from sudmedia_utils import Progress, ProgressReader, format_duration, format_size_short

__all__ = ["Progress", "ProgressReader", "format_duration", "format_size_short"]
