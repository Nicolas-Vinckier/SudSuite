"""Barre de progression universelle et proxy de lecture par octets."""

from __future__ import annotations

import shutil
import sys
import threading
import time
from pathlib import Path

from .formatters import format_duration, format_size_short


class ProgressReader:
    """Proxy qui comptabilise les octets lus dans une instance :class:`Progress`."""

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
    """Compatibilité avec l'ancienne API de progression par palier."""
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
