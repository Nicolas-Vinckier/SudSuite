"""Constantes pour les formats et transformations d'images et de médias."""

IMAGE_EXTENSIONS = (
    ".png",
    ".jpeg",
    ".jpg",
    ".webp",
    ".bmp",
    ".tiff",
    ".gif",
    ".heic",
    ".mpo",
)

VIDEO_EXTENSIONS = (".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv")

MEDIA_EXTENSIONS = IMAGE_EXTENSIONS + VIDEO_EXTENSIONS

RESIZE_METHODS = {
    "1": "Remplissage (Recadrage centré)",
    "2": "Adaptation (Bandes noires/transparentes)",
    "3": "Étirage (Peut déformer l'image)",
}

IMAGE_OUTPUT_FORMATS = {
    "1": ("PNG", ".png"),
    "2": ("JPEG", ".jpg"),
    "3": ("WEBP", ".webp"),
    "4": ("BMP", ".bmp"),
    "5": ("TIFF", ".tiff"),
    "6": ("GIF", ".gif"),
}
