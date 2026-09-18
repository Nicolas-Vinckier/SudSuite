"""Utilitaires partagés par les outils en ligne de commande de SudMedia.

Ce module reste volontairement limité à la bibliothèque standard. Les outils qui
manipulent des images peuvent donc afficher une erreur de dépendance claire sans
empêcher les autres utilitaires (archives, poids de dossiers, etc.) de démarrer.
"""

from __future__ import annotations

import os
import shutil
import sys
import time
import warnings
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path


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

IGNORED_DIRECTORY_NAMES = frozenset(
    {
        ".git",
        ".idea",
        ".next",
        ".venv",
        ".vscode",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "venv",
    }
)


@dataclass(frozen=True)
class SizeAnalysis:
    """Comparaison réutilisable entre une taille source et une taille finale."""

    original_size: int
    final_size: int

    @property
    def variation(self) -> int:
        return self.final_size - self.original_size

    @property
    def saved_bytes(self) -> int:
        return max(0, -self.variation)

    @property
    def increased_bytes(self) -> int:
        return max(0, self.variation)

    @property
    def reduction_percent(self) -> float:
        if self.original_size <= 0:
            return 0.0
        return ((self.original_size - self.final_size) / self.original_size) * 100


@dataclass(frozen=True)
class QualityAnalysis:
    """Niveau de qualité normalisé et estimation lisible de son impact."""

    quality: int
    estimated_loss_percent: int
    risk_level: str
    description: str


@dataclass
class ProcessingStats:
    """Statistiques communes aux traitements de fichiers par lot."""

    total_files: int
    success_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    original_size: int = 0
    final_size: int = 0
    started_at: float = field(default_factory=time.perf_counter)

    def add_success(self, original_size: int, final_size: int) -> None:
        self.success_count += 1
        self.original_size += max(0, int(original_size))
        self.final_size += max(0, int(final_size))

    def add_skipped(self) -> None:
        self.skipped_count += 1

    def add_error(self) -> None:
        self.error_count += 1

    @property
    def elapsed(self) -> float:
        return max(0.0, time.perf_counter() - self.started_at)

    @property
    def size_analysis(self) -> SizeAnalysis:
        return analyze_size_change(self.original_size, self.final_size)


def configure_console_output() -> None:
    """Configure la sortie UTF-8 quand le terminal courant le permet."""
    if sys.platform == "win32":
        # Active le traitement VT100 dans les consoles Windows compatibles.
        os.system("")

    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is None:
        return

    try:
        reconfigure(encoding="utf-8")
    except (AttributeError, LookupError, OSError):
        # Une sortie redirigée ou remplacée (tests, IDE) n'est pas toujours
        # reconfigurable. L'outil reste utilisable avec son encodage courant.
        pass


def configure_pillow(image_module) -> None:
    """Applique la même configuration Pillow à tous les outils d'image."""
    image_module.MAX_IMAGE_PIXELS = None
    warnings.simplefilter("ignore", image_module.DecompressionBombWarning)


def clean_input_path(value: str | None) -> str:
    """Nettoie un chemin saisi ou glissé-déposé dans le terminal."""
    if value is None:
        return ""

    cleaned = value.strip()
    if (
        len(cleaned) >= 2
        and cleaned[0] == cleaned[-1]
        and cleaned[0] in {'"', "'"}
    ):
        cleaned = cleaned[1:-1]
    return cleaned


def paths_overlap(first_path, second_path) -> bool:
    """Indique si deux chemins sont identiques ou imbriqués l'un dans l'autre."""
    first = Path(first_path).expanduser().resolve()
    second = Path(second_path).expanduser().resolve()
    return first == second or first in second.parents or second in first.parents


def format_size(size_in_bytes: int | float) -> str:
    """Formate un nombre d'octets avec les unités françaises de SudMedia."""
    value = float(size_in_bytes)
    for unit in ("O", "Ko", "Mo", "Go", "To"):
        if abs(value) < 1024.0 or unit == "To":
            return f"{value:.2f} {unit}"
        value /= 1024.0

    raise AssertionError("Unité de taille introuvable")


def analyze_size_change(original_size: int, final_size: int) -> SizeAnalysis:
    """Calcule le gain, l'augmentation et le pourcentage entre deux tailles."""
    return SizeAnalysis(
        original_size=max(0, int(original_size)),
        final_size=max(0, int(final_size)),
    )


def normalize_quality(value, default: int = 75) -> int:
    """Convertit une qualité en entier compris entre 1 et 100."""
    try:
        quality = int(value)
    except (TypeError, ValueError):
        quality = int(default)
    return max(1, min(100, quality))


def analyze_quality(value, default: int = 75) -> QualityAnalysis:
    """Classe le risque visuel estimé d'un niveau de compression avec perte."""
    quality = normalize_quality(value, default)
    if quality < 50:
        risk_level = "ÉLEVÉ"
        description = "Artefacts visibles, flou et dégradation possible des couleurs."
    elif quality < 80:
        risk_level = "MODÉRÉ"
        description = "Légère perte de netteté, généralement acceptable pour le web."
    else:
        risk_level = "FAIBLE"
        description = "Perte généralement peu perceptible à l'œil nu."

    return QualityAnalysis(
        quality=quality,
        estimated_loss_percent=100 - quality,
        risk_level=risk_level,
        description=description,
    )


def get_original_image_quality(image, default: int = 100) -> int:
    """Lit la qualité intégrée à une image Pillow lorsqu'elle est disponible."""
    return normalize_quality(image.info.get("quality"), default)


def image_save_options(
    target_format: str,
    *,
    compression_mode: str = "standard",
    quality=None,
    original_quality: int | None = None,
) -> dict:
    """Construit les paramètres Pillow communs pour un format et un mode.

    ``compression_mode`` accepte ``standard``, ``lossless`` ou ``lossy``.
    """
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


def print_quality_analysis(analysis: QualityAnalysis) -> None:
    """Affiche une analyse de qualité homogène dans les outils SudMedia."""
    print(
        f"[Risque {analysis.risk_level}] Qualité {analysis.quality}/100 "
        f"(perte estimée : {analysis.estimated_loss_percent} %)."
    )
    print(f"   {analysis.description}")


def print_processing_summary(
    stats: ProcessingStats,
    *,
    title: str = "BILAN DE L'OPÉRATION",
    item_label: str = "Fichiers traités",
    original_label: str = "Taille initiale",
    final_label: str = "Taille finale",
    output_path: str | os.PathLike[str] | None = None,
    width: int = 45,
    show_duration: bool = True,
) -> None:
    """Affiche un bilan commun avec compteurs, tailles et variation."""
    analysis = stats.size_analysis
    print("\n" + "=" * width)
    print(f"📊 {title}")
    print("=" * width)
    print(f"✅ {item_label} : {stats.success_count}/{stats.total_files}")
    if stats.skipped_count:
        print(f"⏩ Fichiers ignorés : {stats.skipped_count}")
    if stats.error_count:
        print(f"⚠️  Erreurs : {stats.error_count}")
    if show_duration:
        print(f"⏱️  Temps écoulé : {stats.elapsed:.2f} secondes")
    print(f"📦 {original_label} : {format_size(stats.original_size)}")
    print(f"📦 {final_label} : {format_size(stats.final_size)}")

    if analysis.variation < 0:
        print(
            f"📉 Gain d'espace : {format_size(analysis.saved_bytes)} "
            f"({analysis.reduction_percent:.1f} %)"
        )
    elif analysis.variation > 0:
        print(
            f"📈 Augmentation : {format_size(analysis.increased_bytes)} "
            f"({abs(analysis.reduction_percent):.1f} %)"
        )
    else:
        print("➖ Variation : aucune")

    if output_path is not None:
        print(f"📂 Sortie : {output_path}")
    print("=" * width)


def walk_filtered(
    root_path: str | os.PathLike[str],
    ignored_directories: Iterable[str] = IGNORED_DIRECTORY_NAMES,
):
    """Parcourt un dossier en ignorant les répertoires techniques et cachés."""
    ignored = set(ignored_directories)
    for root, directories, filenames in os.walk(root_path, followlinks=False):
        directories[:] = sorted(
            directory
            for directory in directories
            if directory not in ignored
            and not directory.startswith((".", "__"))
        )
        yield root, directories, sorted(filenames)


def collect_target_files(
    paths: Iterable[str | os.PathLike[str]],
    extensions: Iterable[str],
    *,
    item_label: str = "un fichier pris en charge",
    ignored_directories: Iterable[str] = IGNORED_DIRECTORY_NAMES,
    reporter: Callable[[str], None] | None = print,
) -> list[str]:
    """Collecte récursivement des fichiers valides, sans doublon.

    Les chemins retournés conservent leur forme d'origine afin que les dossiers
    de sortie calculés par les scripts restent inchangés.
    """
    normalized_extensions = []
    for extension in extensions:
        normalized_extension = str(extension).lower()
        if not normalized_extension.startswith("."):
            normalized_extension = f".{normalized_extension}"
        normalized_extensions.append(normalized_extension)
    normalized_extensions = tuple(normalized_extensions)
    collected: list[str] = []
    seen: set[str] = set()

    def add_file(file_path: str) -> None:
        identity = os.path.normcase(os.path.realpath(file_path))
        if identity not in seen:
            seen.add(identity)
            collected.append(file_path)

    for raw_path in paths:
        path = clean_input_path(os.fspath(raw_path))
        if not path:
            continue

        if os.path.isdir(path):
            for root, _directories, filenames in walk_filtered(
                path, ignored_directories
            ):
                for filename in filenames:
                    if filename.lower().endswith(normalized_extensions):
                        add_file(os.path.join(root, filename))
        elif os.path.isfile(path):
            if path.lower().endswith(normalized_extensions):
                add_file(path)
            elif reporter:
                reporter(
                    f"⚠️  Le fichier {os.path.basename(path)} n'est pas {item_label}."
                )
        elif reporter:
            reporter(f"❌ '{path}' n'est ni un fichier ni un dossier valide.")

    return collected


def render_progress(
    global_index: int,
    global_total: int,
    filename: str,
    step: int | float = 0,
    total_steps: int | float = 100,
    status: str | None = None,
) -> None:
    """Affiche la barre de progression commune sans dépasser le terminal."""
    columns = max(40, shutil.get_terminal_size(fallback=(80, 20)).columns)
    global_total = max(0, global_total)
    global_ratio = (
        min(1.0, max(0.0, global_index / global_total))
        if global_total
        else 1.0
    )
    step_ratio = (
        min(1.0, max(0.0, step / total_steps)) if total_steps else 1.0
    )

    global_bar_length = 10
    local_bar_length = 10
    global_filled = int(global_bar_length * global_ratio)
    local_filled = int(local_bar_length * step_ratio)
    global_bar = "█" * global_filled + "░" * (global_bar_length - global_filled)
    local_bar = "━" * local_filled + " " * (local_bar_length - local_filled)

    if status:
        prefix = (
            f" G:[{global_bar}] {global_ratio * 100:>3.0f}% | "
            f"{status:<12.12} | D:[{local_bar}] | "
        )
    else:
        prefix = (
            f" G:[{global_bar}] {global_ratio * 100:>3.0f}% "
            f"({global_index}/{global_total}) | D:[{local_bar}] | "
        )

    available = max(5, columns - len(prefix) - 1)
    short_name = Path(filename).name
    if len(short_name) > available:
        short_name = short_name[: max(2, available - 3)] + "..."

    line = (prefix + short_name)[: columns - 1]
    sys.stdout.write("\r" + line.ljust(columns - 1))
    sys.stdout.flush()


def reserve_output_path(
    output_path: str | os.PathLike[str],
    reserved_paths: set[str] | None = None,
) -> str:
    """Réserve un nom unique au sein d'un traitement par lot.

    Les fichiers déjà présents sur le disque ne sont pas renommés ici : chaque
    outil conserve ainsi sa politique existante (écrasement, saut ou suffixe).
    """
    candidate = Path(output_path)
    if reserved_paths is None:
        return str(candidate)

    def identity(path: Path) -> str:
        return os.path.normcase(os.path.abspath(path))

    candidate_identity = identity(candidate)
    if candidate_identity not in reserved_paths:
        reserved_paths.add(candidate_identity)
        return str(candidate)

    counter = 2
    while True:
        numbered = candidate.with_name(
            f"{candidate.stem}_{counter}{candidate.suffix}"
        )
        numbered_identity = identity(numbered)
        if numbered_identity not in reserved_paths:
            reserved_paths.add(numbered_identity)
            return str(numbered)
        counter += 1


def unique_available_path(output_path: str | os.PathLike[str]) -> str:
    """Renvoie un chemin libre sur le disque en ajoutant un index si nécessaire."""
    candidate = Path(output_path)
    if not candidate.exists():
        return str(candidate)

    counter = 2
    while True:
        numbered = candidate.with_name(
            f"{candidate.stem}_{counter}{candidate.suffix}"
        )
        if not numbered.exists():
            return str(numbered)
        counter += 1


def resize_image(image, target_width, target_height, method="1"):
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
