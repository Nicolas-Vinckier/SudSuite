"""Configuration Pillow et préparation des images."""

from __future__ import annotations

import warnings

from ..metrics.quality import normalize_quality


def configure_pillow(image_module) -> None:
    """Applique la même configuration Pillow à tous les outils d'image."""
    image_module.MAX_IMAGE_PIXELS = None
    warnings.simplefilter("ignore", image_module.DecompressionBombWarning)


def get_original_image_quality(image, default: int = 100) -> int:
    """Lit la qualité intégrée à une image Pillow lorsqu'elle est disponible."""
    return normalize_quality(image.info.get("quality"), default)


def prepare_image_for_format(image, target_format: str):
    """Adapte le mode Pillow au format cible, avec un fond blanc pour JPEG."""
    from PIL import Image

    normalized_format = target_format.upper()
    if normalized_format in {"JPG", "JPEG"} and image.mode in {"RGBA", "LA", "P"}:
        rgba_image = image.convert("RGBA")
        background = Image.new("RGB", rgba_image.size, "white")
        background.paste(rgba_image, mask=rgba_image.getchannel("A"))
        return background

    if normalized_format != "GIF" and image.mode == "P":
        return image.convert("RGBA" if "transparency" in image.info else "RGB")

    if normalized_format == "WEBP" and image.mode not in {"RGB", "RGBA"}:
        target_mode = "RGBA" if "A" in image.getbands() else "RGB"
        return image.convert(target_mode)

    return image


def prepare_image_for_quality(
    image,
    target_format: str,
    *,
    compression_mode: str = "standard",
    quality=None,
):
    """Applique les transformations de pixels nécessaires avant sauvegarde."""
    image = prepare_image_for_format(image, target_format)
    if compression_mode == "lossy" and target_format.upper() == "PNG":
        from PIL import Image

        normalized_quality = normalize_quality(quality, 75)
        colors = max(2, int((normalized_quality / 100) * 256))
        return image.convert("P", palette=Image.Palette.ADAPTIVE, colors=colors)
    return image


def image_save_options(
    target_format: str,
    *,
    compression_mode: str = "standard",
    quality=None,
    original_quality: int | None = None,
) -> dict:
    """Construit les paramètres Pillow communs pour un format et un mode."""
    normalized_format = target_format.upper()
    if normalized_format == "JPG":
        normalized_format = "JPEG"
    if compression_mode not in {"standard", "lossless", "lossy"}:
        raise ValueError(f"Mode de compression inconnu : {compression_mode}")

    if compression_mode == "lossy":
        normalized_quality = normalize_quality(quality, 75)
        if normalized_format == "JPEG":
            return {"optimize": True, "quality": normalized_quality}
        if normalized_format == "WEBP":
            return {"quality": normalized_quality, "method": 4}
        if normalized_format == "PNG":
            return {"optimize": True}
        return {}

    if compression_mode == "lossless":
        if normalized_format == "JPEG":
            preserved_quality = normalize_quality(original_quality, 100)
            return {
                "optimize": True,
                "quality": preserved_quality,
                "subsampling": 0,
            }
        if normalized_format == "WEBP":
            return {"lossless": True, "quality": 100, "method": 6}
        if normalized_format == "PNG":
            return {"optimize": True}
        return {}

    if normalized_format == "JPEG":
        return {
            "quality": normalize_quality(quality, 95),
            "subsampling": 0,
        }
    if normalized_format == "WEBP":
        return {"lossless": True, "quality": 100}
    if normalized_format == "PNG":
        return {"optimize": True}
    return {}
