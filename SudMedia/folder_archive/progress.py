"""Affichage de progression commun aux moteurs d'archive."""

import shutil
import sys
import threading
import time

try:
    from ..sudmedia_utils import format_size
except ImportError:
    from sudmedia_utils import format_size


def format_size_short(size_in_bytes):
    value = float(size_in_bytes)
    for unit in ["O", "K", "M", "G", "T"]:
        if value < 1024.0 or unit == "T":
            if value >= 100:
                return f"{value:.0f}{unit}"
            if value >= 10:
                return f"{value:.1f}{unit}"
            return f"{value:.2f}{unit}"
        value /= 1024.0


def format_duration(seconds):
    if seconds is None:
        return "--:--"
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


class ProgressReader:
    """Proxy de lecture qui comptabilise les octets envoyes a l'archive TAR."""

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
    """Progression combinee taille/fichiers, avec debit et estimation restante."""

    BAR_LENGTH = 24
    REFRESH_INTERVAL = 0.12

    def __init__(self, total_files, total_bytes, label="Compression", enabled=True):
        self.total_files = max(0, total_files)
        self.total_bytes = max(0, total_bytes)
        self.label = label
        self.enabled = enabled and (self.total_files > 0 or self.total_bytes > 0)
        self.completed_files = 0
        self.processed_bytes = 0
        self.external_ratio = None
        self.approximate_counts = False
        self.started_at = time.monotonic()
        self.last_render_at = 0.0
        self.last_speed_at = self.started_at
        self.last_speed_bytes = 0
        self.smoothed_speed = 0.0
        self.last_line_length = 0
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.refresh_thread = None
        self.full_block = "█"
        self.empty_block = "░"

        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        try:
            (self.full_block + self.empty_block).encode(encoding)
        except (LookupError, UnicodeEncodeError):
            self.full_block = "#"
            self.empty_block = "-"

    def start(self):
        if not self.enabled:
            return
        self._render(force=True)
        self.refresh_thread = threading.Thread(
            target=self._refresh_until_stopped,
            name="sudmedia-progress",
            daemon=True,
        )
        self.refresh_thread.start()

    def _refresh_until_stopped(self):
        while not self.stop_event.wait(0.25):
            self._render(force=True)

    def update_bytes(self, byte_count):
        with self.lock:
            if byte_count > 0:
                self.processed_bytes = min(self.total_bytes, self.processed_bytes + byte_count)
                self._update_speed(time.monotonic())
        self._render()

    def complete_file(self, missing_bytes=0):
        with self.lock:
            if missing_bytes > 0:
                self.processed_bytes = min(self.total_bytes, self.processed_bytes + missing_bytes)
                self._update_speed(time.monotonic())
            self.completed_files = min(self.total_files, self.completed_files + 1)
        self._render()

    def update_external(self, percent):
        with self.lock:
            ratio = min(1.0, max(0.0, percent / 100.0))
            if self.external_ratio is not None:
                ratio = max(self.external_ratio, ratio)
            self.external_ratio = ratio
            self.approximate_counts = True
            self.processed_bytes = max(self.processed_bytes, int(self.total_bytes * ratio))
            self.completed_files = max(
                self.completed_files,
                min(self.total_files, int(self.total_files * ratio)),
            )
            self._update_speed(time.monotonic())
        self._render()

    def _ratio(self):
        if self.external_ratio is not None:
            return self.external_ratio
        file_ratio = self.completed_files / self.total_files if self.total_files else 1.0
        byte_ratio = self.processed_bytes / self.total_bytes if self.total_bytes else 1.0
        if self.total_files and self.total_bytes:
            return (byte_ratio * 0.90) + (file_ratio * 0.10)
        return byte_ratio if self.total_bytes else file_ratio

    def _update_speed(self, now):
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

    def _render(self, force=False):
        if not self.enabled:
            return
        with self.lock:
            now = time.monotonic()
            if not force and (now - self.last_render_at) < self.REFRESH_INTERVAL:
                return
            self._update_speed(now)
            self.last_render_at = now
            ratio = min(1.0, self._ratio())
            percent = ratio * 100.0
            elapsed = max(0.0, now - self.started_at)
            eta = elapsed * (1.0 - ratio) / ratio if ratio > 0 and elapsed >= 0.25 else None
            count_prefix = "~" if self.approximate_counts and ratio < 1.0 else ""
            speed_is_recent = (now - self.last_speed_at) <= 2.0
            speed = f"{format_size(self.smoothed_speed)}/s" if self.smoothed_speed and speed_is_recent else "--"
            terminal_width = max(40, shutil.get_terminal_size(fallback=(120, 24)).columns - 1)
            line = self._build_line(
                terminal_width,
                ratio,
                percent,
                count_prefix,
                speed,
                elapsed,
                format_duration(eta) if eta is not None else "--:--",
            )
            padding = " " * max(0, min(self.last_line_length, terminal_width) - len(line))
            print(f"\r{line}{padding}", end="", flush=True)
            self.last_line_length = len(line)

    def _build_line(self, terminal_width, ratio, percent, count_prefix, speed, elapsed, remaining):
        processed = format_size(self.processed_bytes).replace(" ", "")
        total = format_size(self.total_bytes).replace(" ", "")
        speed = speed.replace(" ", "")
        prefix = f"[{self.label}] |"
        suffix = (
            f"| {percent:5.1f}% | {count_prefix}{self.completed_files}/{self.total_files} fich. | "
            f"{processed}/{total} | {speed} | Ecoule {format_duration(elapsed)} | ETA ~{remaining}"
        )
        available_for_bar = terminal_width - len(prefix) - len(suffix)
        if available_for_bar >= 6:
            bar_length = min(self.BAR_LENGTH, available_for_bar)
            filled = int(bar_length * ratio)
            bar = self.full_block * filled + self.empty_block * (bar_length - filled)
            return f"{prefix}{bar}{suffix}"

        processed_short = format_size_short(self.processed_bytes)
        total_short = format_size_short(self.total_bytes)
        speed_short = f"{format_size_short(self.smoothed_speed)}/s" if speed != "--" else "--"
        compact_prefix = "[C]|"
        compact_suffix = (
            f"|{percent:.0f}% {count_prefix}{self.completed_files}/{self.total_files}f "
            f"{processed_short}/{total_short} {speed_short} E{format_duration(elapsed)} R~{remaining}"
        )
        bar_length = max(1, min(12, terminal_width - len(compact_prefix) - len(compact_suffix)))
        filled = int(bar_length * ratio)
        line = f"{compact_prefix}{self.full_block * filled}{self.empty_block * (bar_length - filled)}{compact_suffix}"
        return line[:terminal_width]

    def _stop_refresh(self):
        self.stop_event.set()
        if self.refresh_thread and self.refresh_thread.is_alive():
            self.refresh_thread.join(timeout=1.0)

    def finish(self):
        if self.enabled:
            self._stop_refresh()
            with self.lock:
                self.processed_bytes = self.total_bytes
                self.completed_files = self.total_files
                self.external_ratio = 1.0 if self.external_ratio is not None else None
            self._render(force=True)
            print()

    def abort(self):
        if self.enabled and self.last_line_length:
            self._stop_refresh()
            print()
