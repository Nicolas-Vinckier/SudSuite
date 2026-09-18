"""Redimensionnement et transformation géométrique d'images."""

from __future__ import annotations


def resize_image(image, target_width: int | None, target_height: int | None, method: str = "1"):
    """Redimensionne une image avec les méthodes communes aux outils SudMedia."""
    from PIL import Image

    source_width, source_height = image.size
    if target_width is not None and target_height is None:
        target_height = max(
            1, int(round(source_height * (target_width / source_width)))
        )
        return image.resize(
            (target_width, target_height), Image.Resampling.LANCZOS
        )
    if target_height is not None and target_width is None:
        target_width = max(
            1, int(round(source_width * (target_height / source_height)))
        )
        return image.resize(
            (target_width, target_height), Image.Resampling.LANCZOS
        )
    if target_width is None or target_height is None:
        return image

    if method == "1":
        source_ratio = source_width / source_height
        target_ratio = target_width / target_height
        if source_ratio > target_ratio:
            resized_height = target_height
            resized_width = int(source_width * (target_height / source_height))
            image = image.resize(
                (resized_width, resized_height), Image.Resampling.LANCZOS
            )
            left = (resized_width - target_width) // 2
            return image.crop((left, 0, left + target_width, target_height))

        resized_width = target_width
        resized_height = int(source_height * (target_width / source_width))
        image = image.resize(
            (resized_width, resized_height), Image.Resampling.LANCZOS
        )
        top = (resized_height - target_height) // 2
        return image.crop((0, top, target_width, top + target_height))

    if method == "2":
        image.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (target_width, target_height), (0, 0, 0, 0))
        offset = (
            (target_width - image.width) // 2,
            (target_height - image.height) // 2,
        )
        if image.mode == "RGBA":
            canvas.paste(image, offset, image)
        else:
            canvas.paste(image, offset)
        return canvas

    return image.resize(
        (target_width, target_height), Image.Resampling.LANCZOS
    )
