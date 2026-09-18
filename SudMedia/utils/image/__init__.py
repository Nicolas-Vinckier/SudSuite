"""Module image : extensions multimédias, configuration Pillow, redimensionnement et sauvegarde."""

from .constants import (
    IMAGE_EXTENSIONS,
    IMAGE_OUTPUT_FORMATS,
    MEDIA_EXTENSIONS,
    RESIZE_METHODS,
    VIDEO_EXTENSIONS,
)
from .pillow import (
    configure_pillow,
    get_original_image_quality,
    image_save_options,
    prepare_image_for_format,
    prepare_image_for_quality,
)
from .resize import resize_image

__all__ = [
    "IMAGE_EXTENSIONS",
    "IMAGE_OUTPUT_FORMATS",
    "MEDIA_EXTENSIONS",
    "RESIZE_METHODS",
    "VIDEO_EXTENSIONS",
    "configure_pillow",
    "get_original_image_quality",
    "image_save_options",
    "prepare_image_for_format",
    "prepare_image_for_quality",
    "resize_image",
]
