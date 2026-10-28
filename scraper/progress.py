"""Baris progres di terminal yang terus diperbarui, plus logging ke file.

- Terminal (bila stderr adalah terminal): satu baris progres yang ditimpa terus, mis.
    [scraping] ███████░░░░░░░░░░░░░ 137/612 (22%) | tokopedia: kabel eterna | 4.321 produk | sisa ±25 mnt
  Pesan log yang tampil di terminal (peringatan/error, atau semua dengan -v) dicetak di
  atasnya tanpa merusak baris progres.
- File log: semua pesan (INFO; DEBUG dengan -v), ditambahkan ke akhir file.
- Bila stderr dialihkan ke file (`> log 2>&1`), baris progres tidak digambar.
"""
from __future__ import annotations

import logging
import shutil
import sys
import threading
from pathlib import Path


def bar(done: int, total: int, width: int = 20) -> str:
    filled = round(width * done / total) if total else 0
    return "█" * filled + "░" * (width - filled)


class ProgressLine:
    def __init__(self, stream=sys.stderr) -> None:
        self.stream = stream
        self.enabled = hasattr(stream, "isatty") and stream.isatty()
        self.lock = threading.RLock()
        self.text = ""

    def _clear(self) -> None:
        self.stream.write("\r\x1b[2K")

    def _draw(self) -> None:
        if self.text:
            width = shutil.get_terminal_size((120, 20)).columns
            self.stream.write(self.text[: max(width - 1, 20)])
        self.stream.flush()

    def set(self, text: str) -> None:
        if not self.enabled:
            return
        with self.lock:
            self.text = text
            self._clear()
            self._draw()

    def finish(self) -> None:
        """Tinggalkan baris progres terakhir di layar dan pindah ke baris baru."""
        if not self.enabled:
            return
        with self.lock:
            if self.text:
                self._clear()
                self._draw()
                self.stream.write("\n")
                self.stream.flush()
            self.text = ""


class _ConsoleHandler(logging.StreamHandler):
    """Mencetak pesan log di atas baris progres, lalu menggambar ulang baris progresnya."""

    def __init__(self, line: ProgressLine) -> None:
        super().__init__(line.stream)
        self.line = line

    def emit(self, record: logging.LogRecord) -> None:
        with self.line.lock:
            if self.line.enabled and self.line.text:
                self.line._clear()
            super().emit(record)
            if self.line.enabled:
                self.line._draw()


# Satu objek bersama untuk seluruh proses.
line = ProgressLine()


def setup_logging(verbose: bool, log_file: Path | None) -> None:
    """File log: INFO (DEBUG dengan -v). Terminal: pesan penting, peringatan & error bila
    ada baris progres dan file log (semua pesan dengan -v); tanpa terminal: semua INFO."""
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    for h in list(root.handlers):
        root.removeHandler(h)

    console = _ConsoleHandler(line)
    console.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S"))
    if verbose:
        console.setLevel(logging.DEBUG)
    elif line.enabled and log_file:
        console.setLevel(25)  # pesan say() + peringatan & error
    else:
        console.setLevel(logging.INFO)
    root.addHandler(console)

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S"))
        fh.setLevel(logging.DEBUG if verbose else logging.INFO)
        root.addHandler(fh)

    logging.getLogger("httpx").setLevel(logging.WARNING)


def say(message: str) -> None:
    """Pesan penting untuk pengguna: tampil di terminal (di atas baris progres) dan masuk log."""
    logging.getLogger("scraper").log(25, message)  # 25 = di antara INFO dan WARNING


logging.addLevelName(25, "INFO")
