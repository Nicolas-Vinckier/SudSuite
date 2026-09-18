"""Utilitaires partagés par les outils en ligne de commande de SudMedia.

Ce module reste volontairement limité à la bibliothèque standard. Les outils qui
manipulent des images peuvent donc afficher une erreur de dépendance claire sans
empêcher les autres utilitaires (archives, poids de dossiers, etc.) de démarrer.
"""

from __future__ import annotations

import os
import shutil
import sys
import threading
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


def format_size_short(size_in_bytes: int | float) -> str:
    """Formate une taille de façon compacte pour les barres étroites."""
    value = float(size_in_bytes)
    for unit in ("O", "K", "M", "G", "T"):
        if abs(value) < 1024.0 or unit == "T":
            if abs(value) >= 100:
                return f"{value:.0f}{unit}"
            if abs(value) >= 10:
                return f"{value:.1f}{unit}"
            return f"{value:.2f}{unit}"
        value /= 1024.0
    raise AssertionError("Unité de taille introuvable")


def format_duration(seconds: float | None) -> str:
    """Formate une durée pour la progression et son estimation restante."""
    if seconds is None:
        return "--:--"
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


class ProgressReader:
    """Proxy qui comptabilise les octets lus dans une :class:`Progress`."""

    def __init__(self, source, progress):
        self.source = source
        self.progress = progress
        self.bytes_read = 0

    def read(self, size=-1):
        data = self.source.read(size)
        self.bytes_read += len(data)
        self.progress.update_bytes(len(data))
        return data


class Progress:
    """Barre de progression unique pour tous les traitements SudMedia.

    Elle accepte un nombre de fichiers, un volume d'octets ou un travail de
    taille inconnue. Les archives peuvent mettre à jour les octets tandis que
    les outils d'image utilisent les fichiers et les étapes intermédiaires.
    """

    BAR_LENGTH = 24
    REFRESH_INTERVAL = 0.12
    SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def __init__(
        self,
        total_files: int | None = 0,
        total_bytes: int | None = 0,
        label: str = "Traitement",
        enabled: bool = True,
    ):
        self.total_files = max(0, int(total_files or 0))
        self.total_bytes = max(0, int(total_bytes or 0))
        self.indeterminate = total_files is None and not self.total_bytes
        self.label = label
        self.enabled = enabled
        self.completed_files = 0
        self.processed_bytes = 0
        self.external_ratio = None
        self.manual_ratio = None
        self.approximate_counts = False
        self.current_item = ""
        self.status = ""
        self.started_at = time.monotonic()
        self.last_render_at = 0.0
        self.last_speed_at = self.started_at
        self.last_speed_bytes = 0
        self.smoothed_speed = 0.0
        self.last_line_length = 0
        self.spinner_index = 0
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.refresh_thread = None
        self.full_block = "█"
        self.empty_block = "░"

        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        try:
            (self.full_block + self.empty_block + self.SPINNER).encode(encoding)
        except (LookupError, UnicodeEncodeError):
            self.full_block = "#"
            self.empty_block = "-"
            self.SPINNER = "|/-\\"

    def start(self) -> "Progress":
        if not self.enabled:
            return self
        self._render(force=True)
        self.refresh_thread = threading.Thread(
            target=self._refresh_until_stopped,
            name="sudmedia-progress",
            daemon=True,
        )
        self.refresh_thread.start()
        return self

    def _refresh_until_stopped(self) -> None:
        while not self.stop_event.wait(0.25):
            self._render(force=True)

    def set_item(self, item=None, status=None) -> None:
        """Met à jour le fichier et l'étape affichés sans avancer le compteur."""
        with self.lock:
            if item is not None:
                self.current_item = Path(item).name
            if status is not None:
                self.status = str(status)
        self._render(force=True)

    def update_item(
        self,
        completed_files: int | None = None,
        *,
        item=None,
        status=None,
        step: int | float | None = None,
        total_steps: int | float = 100,
    ) -> None:
        """Positionne la progression d'un lot et, éventuellement, de l'étape courante."""
        with self.lock:
            if completed_files is not None:
                value = max(0, int(completed_files))
                self.completed_files = min(self.total_files, value) if self.total_files else value
            if item is not None:
                self.current_item = Path(item).name
            if status is not None:
                self.status = str(status)
            if step is not None and self.total_files:
                step_ratio = min(1.0, max(0.0, float(step) / float(total_steps or 1)))
                self.manual_ratio = min(
                    1.0,
                    (self.completed_files + step_ratio) / self.total_files,
                )
        self._render(force=True)

    def update_bytes(self, byte_count: int) -> None:
        with self.lock:
            if byte_count > 0:
                self.processed_bytes = (
                    min(self.total_bytes, self.processed_bytes + byte_count)
                    if self.total_bytes
                    else self.processed_bytes + byte_count
                )
                self._update_speed(time.monotonic())
        self._render()

    def advance(self, count: int = 1, *, item=None, status=None, byte_count: int = 0) -> None:
        """Avance un traitement connu ou indéterminé."""
        with self.lock:
            if item is not None:
                self.current_item = Path(item).name
            if status is not None:
                self.status = str(status)
            self.completed_files = (
                min(self.total_files, self.completed_files + count)
                if self.total_files
                else self.completed_files + count
            )
            self.manual_ratio = None
        if byte_count:
            self.update_bytes(byte_count)
        else:
            self._render()

    def complete_file(self, missing_bytes=0, *, item=None, status=None) -> None:
        self.advance(1, item=item, status=status, byte_count=max(0, missing_bytes))

    complete_item = complete_file

    def update_external(self, percent: int | float) -> None:
        with self.lock:
            ratio = min(1.0, max(0.0, float(percent) / 100.0))
            if self.external_ratio is not None:
                ratio = max(self.external_ratio, ratio)
            self.external_ratio = ratio
            self.manual_ratio = None
            self.approximate_counts = True
            self.processed_bytes = max(self.processed_bytes, int(self.total_bytes * ratio))
            self.completed_files = max(
                self.completed_files,
                min(self.total_files, int(self.total_files * ratio)),
            )
            self._update_speed(time.monotonic())
        self._render()

    def _ratio(self) -> float | None:
        if self.indeterminate:
            return None
        if self.manual_ratio is not None:
            return self.manual_ratio
        if self.external_ratio is not None:
            return self.external_ratio
        file_ratio = self.completed_files / self.total_files if self.total_files else None
        byte_ratio = self.processed_bytes / self.total_bytes if self.total_bytes else None
        if file_ratio is not None and byte_ratio is not None:
            return (byte_ratio * 0.90) + (file_ratio * 0.10)
        if byte_ratio is not None:
            return byte_ratio
        if file_ratio is not None:
            return file_ratio
        return 0.0

    def _update_speed(self, now: float) -> None:
        elapsed = now - self.last_speed_at
        if elapsed < self.REFRESH_INTERVAL:
            return
        byte_delta = self.processed_bytes - self.last_speed_bytes
        if byte_delta > 0:
            instant_speed = byte_delta / elapsed
            self.smoothed_speed = (
                (self.smoothed_speed * 0.70) + (instant_speed * 0.30)
                if self.smoothed_speed
                else instant_speed
            )
            self.last_speed_at = now
            self.last_speed_bytes = self.processed_bytes

    def _render(self, force=False) -> None:
        if not self.enabled:
            return
        with self.lock:
            now = time.monotonic()
            if not force and (now - self.last_render_at) < self.REFRESH_INTERVAL:
                return
            self._update_speed(now)
            self.last_render_at = now
            ratio = self._ratio()
            elapsed = max(0.0, now - self.started_at)
            eta = (
                elapsed * (1.0 - ratio) / ratio
                if ratio is not None and ratio > 0 and elapsed >= 0.25
                else None
            )
            terminal_width = max(40, shutil.get_terminal_size(fallback=(120, 24)).columns - 1)
            line = self._build_line(terminal_width, ratio, elapsed, eta)
            padding = " " * max(0, min(self.last_line_length, terminal_width) - len(line))
            print(f"\r{line}{padding}", end="", flush=True)
            self.last_line_length = len(line)

    def _build_line(self, terminal_width, ratio, elapsed, eta) -> str:
        details = []
        if self.status:
            details.append(self.status)
        if self.current_item:
            details.append(self.current_item)
        detail_text = " | ".join(details)

        if ratio is None:
            spinner = self.SPINNER[self.spinner_index % len(self.SPINNER)]
            moving_width = min(12, self.BAR_LENGTH)
            position = self.spinner_index % moving_width
            moving_bar = (
                self.empty_block * position
                + self.full_block
                + self.empty_block * (moving_width - position - 1)
            )
            self.spinner_index += 1
            line = (
                f"[{self.label}] |{moving_bar}| {spinner} | "
                f"{self.completed_files} élément(s) | "
                f"Écoulé {format_duration(elapsed)}"
            )
            if detail_text:
                line += f" | {detail_text}"
            return line[:terminal_width]

        ratio = min(1.0, max(0.0, ratio))
        percent = ratio * 100.0
        count_prefix = "~" if self.approximate_counts and ratio < 1.0 else ""
        count = (
            f"{count_prefix}{self.completed_files}/{self.total_files}"
            if self.total_files
            else ""
        )
        byte_text = ""
        if self.total_bytes:
            byte_text = f"{format_size_short(self.processed_bytes)}/{format_size_short(self.total_bytes)}"
        speed = (
            f"{format_size_short(self.smoothed_speed)}/s"
            if self.smoothed_speed and (time.monotonic() - self.last_speed_at) <= 2.0
            else ""
        )
        suffix_parts = [f"{percent:5.1f}%"]
        if count:
            suffix_parts.append(count)
        if byte_text:
            suffix_parts.append(byte_text)
        if speed:
            suffix_parts.append(speed)
        suffix_parts.append(f"ETA ~{format_duration(eta)}")
        if detail_text:
            suffix_parts.append(detail_text)
        suffix = " | " + " | ".join(suffix_parts)
        prefix = f"[{self.label}] |"
        bar_length = max(1, min(self.BAR_LENGTH, terminal_width - len(prefix) - len(suffix) - 1))
        filled = int(bar_length * ratio)
        bar = self.full_block * filled + self.empty_block * (bar_length - filled)
        return f"{prefix}{bar}{suffix}"[:terminal_width]

    def _stop_refresh(self) -> None:
        self.stop_event.set()
        if self.refresh_thread and self.refresh_thread.is_alive():
            self.refresh_thread.join(timeout=1.0)

    def finish(self, *, status="Terminé") -> None:
        if not self.enabled:
            return
        self._stop_refresh()
        with self.lock:
            if not self.indeterminate:
                self.processed_bytes = self.total_bytes
                self.completed_files = self.total_files
                self.manual_ratio = 1.0
                self.external_ratio = 1.0 if self.external_ratio is not None else None
            self.status = status
        self._render(force=True)
        print()

    def abort(self, *, status="Interrompu") -> None:
        if not self.enabled:
            return
        self._stop_refresh()
        self.status = status
        self._render(force=True)
        print()


def render_progress(
    global_index: int,
    global_total: int,
    filename: str,
    step: int | float = 0,
    total_steps: int | float = 100,
    status: str | None = None,
) -> None:
    """Compatibilité avec l'ancienne API, rendue par la barre commune."""
    progress = Progress(global_total, label="Traitement")
    progress.completed_files = max(0, min(progress.total_files, global_index))
    progress.current_item = Path(filename).name
    progress.status = status or ""
    if progress.total_files:
        local_ratio = min(1.0, max(0.0, float(step) / float(total_steps or 1)))
        progress.manual_ratio = min(
            1.0,
            (progress.completed_files + local_ratio) / progress.total_files,
        )
    progress._render(force=True)


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
