"""Progres yang tersimpan terus selama scraping, supaya proses bisa dilanjutkan.

Untuk output `X.xlsx` ada dua file pendamping:
- `X.xlsx.progres.jsonl`: jurnal, satu baris JSON per kejadian, langsung di-flush ke disk.
    {"type": "meta", ...}                         pengaturan jalan (dicek saat melanjutkan)
    {"type": "task", "site", "keyword", "products": [...]}   satu kata kunci×situs selesai
    {"type": "desc", "url", "description"}        satu deskripsi selesai diambil
  Kata kunci yang gagal tidak dicatat, jadi otomatis dicoba lagi saat dilanjutkan.
- `X_PROGRES.txt`: ringkasan yang mudah dibaca (sudah berapa dari berapa, perintah lanjut).

Jalankan ulang perintah yang sama untuk melanjutkan; `--ulang` untuk mulai dari awal.
"""
from __future__ import annotations

import json
import logging
import os
import shlex
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from .models import Product
from .progress import bar

log = logging.getLogger(__name__)

# Pengaturan yang mengubah isi hasil; kalau berbeda dari jalan sebelumnya, jangan dicampur.
META_KEYS = ("mode", "pages", "mitra10_store", "sort", "min_price", "source_file")
FIELDS = set(Product.columns())


class SettingsChanged(RuntimeError):
    pass


class Checkpoint:
    def __init__(self, output: Path, meta: dict, fresh: bool = False) -> None:
        self.output = output
        self.journal_path = output.with_name(output.name + ".progres.jsonl")
        self.status_path = output.with_name(output.stem + "_PROGRES.txt")
        self.tasks: dict[tuple[str, str], list[Product]] = {}
        self.desc: dict[str, str] = {}  # url -> deskripsi ("" = halaman tanpa deskripsi)
        self._lock = threading.Lock()
        self._started = time.time()
        self.resumed_tasks = 0
        self.resumed_desc = 0
        # Ringkasan progres untuk file status
        self.total_tasks = 0
        self.failures: list[str] = []
        self.desc_plan: dict[str, int] = {}
        self.desc_done: dict[str, int] = {}
        self._session_tasks = 0
        self._session_desc = 0
        self._last_status = 0.0
        self._sites: list[str] = []
        self._keywords: list[str] = []
        self._task_set: set[tuple[str, str]] = set()
        self._desc_site = ""
        # Dipanggil setiap ada kemajuan (mis. untuk menggambar ulang baris progres di terminal).
        self.on_change = None

        if fresh:
            for p in (self.journal_path, self.status_path):
                p.unlink(missing_ok=True)
        if self.journal_path.exists():
            self._load(meta)
        output.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.journal_path.open("a", encoding="utf-8")
        if not self.resumed_tasks and not self.resumed_desc and self.journal_path.stat().st_size == 0:
            self._append({"type": "meta", **{k: meta.get(k) for k in META_KEYS}})

    # ------------------------------------------------------------------ baca jurnal
    def _load(self, meta: dict) -> None:
        with self.journal_path.open(encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    # Baris terakhir bisa terpotong bila proses dihentikan saat menulis.
                    log.warning("[lanjut] baris %d jurnal rusak, dilewati", n)
                    continue
                kind = rec.get("type")
                if kind == "meta":
                    diff = {k: (rec.get(k), meta.get(k)) for k in META_KEYS if rec.get(k) != meta.get(k)}
                    if diff:
                        detail = ", ".join(f"{k}: sebelumnya {a!r}, sekarang {b!r}" for k, (a, b) in diff.items())
                        raise SettingsChanged(
                            f"Pengaturan berbeda dari jalan sebelumnya untuk {self.output} ({detail}). "
                            "Pakai pengaturan yang sama untuk melanjutkan, nama output lain, "
                            "atau --ulang untuk mulai dari awal."
                        )
                elif kind == "task":
                    products = [Product(**{k: v for k, v in d.items() if k in FIELDS}) for d in rec["products"]]
                    self.tasks[(rec["site"], rec["keyword"])] = products
                elif kind == "desc":
                    self.desc[rec["url"]] = rec["description"] or ""
        self.resumed_tasks = len(self.tasks)
        self.resumed_desc = len(self.desc)

    # ------------------------------------------------------------------ tulis jurnal
    def _append(self, rec: dict) -> None:
        with self._lock:
            self._fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            self._fh.flush()
            os.fsync(self._fh.fileno())

    def is_done(self, site: str, keyword: str) -> bool:
        return (site, keyword) in self.tasks

    def add_task(self, site: str, keyword: str, products: list[Product]) -> None:
        self._append({"type": "task", "site": site, "keyword": keyword,
                      "products": [p.to_dict() for p in products]})
        self.tasks[(site, keyword)] = products
        self._session_tasks += 1
        self._changed()

    def products_for(self, tasks: list[tuple[str, str]]) -> list[Product]:
        """Produk dari kata kunci×situs yang sudah selesai, urut sesuai daftar tugas sekarang."""
        out = []
        for t in tasks:
            out.extend(self.tasks.get(t, []))
        for p in out:
            if p.url in self.desc and not p.description:
                p.description = self.desc[p.url] or None
        return out

    # ------------------------------------------------------------------ deskripsi (dipanggil dari thread)
    def start(self, site: str, total: int, done: int = 0) -> None:
        """`total` = semua halaman yang direncanakan, `done` = yang sudah ada dari jalan sebelumnya."""
        self.desc_plan[site] = total
        self.desc_done[site] = done
        self._desc_site = site
        self.write_status(phase="deskripsi", force=True)
        self._changed()

    def result(self, site: str, url: str, text: str | None) -> None:
        self._append({"type": "desc", "url": url, "description": text or ""})
        with self._lock:
            self.desc[url] = text or ""
            self.desc_done[site] = self.desc_done.get(site, 0) + 1
            self._session_desc += 1
        self.write_status(phase="deskripsi")
        self._changed()

    def _changed(self) -> None:
        if self.on_change:
            self.on_change()

    # ------------------------------------------------------------------ status
    def tasks_done(self) -> int:
        return sum(1 for t in self.tasks if t in self._task_set)

    def summary_line(self, phase: str, current: str = "") -> str:
        """Satu baris ringkas untuk terminal."""
        elapsed = int(time.time() - self._started)
        jalan = f"jalan {elapsed // 3600}j{elapsed % 3600 // 60:02d}m" if elapsed >= 3600 else f"jalan {elapsed // 60}m{elapsed % 60:02d}d"
        if phase == "scraping":
            done, total = self.tasks_done(), self.total_tasks
            n_products = sum(len(v) for t, v in self.tasks.items() if t in self._task_set)
            parts = [f"[scraping] {bar(done, total)} {done}/{total} ({done * 100 // max(total, 1)}%)"]
            if current:
                parts.append(current)
            parts += [f"{n_products:,} produk".replace(",", "."), jalan,
                      f"sisa {self._eta(total - done, self._session_tasks)}"]
            if self.failures:
                parts.append(f"gagal {len(self.failures)}")
            return " | ".join(parts)
        site = self._desc_site
        total, done = self.desc_plan.get(site, 0), self.desc_done.get(site, 0)
        remaining = sum(self.desc_plan.values()) - sum(self.desc_done.get(s, 0) for s in self.desc_plan)
        return " | ".join([f"[deskripsi {site}] {bar(done, total)} {done}/{total} ({done * 100 // max(total, 1)}%)",
                           jalan, f"sisa {self._eta(remaining, self._session_desc)}"])

    def _eta(self, remaining: int, done_this_session: int) -> str:
        if not remaining:
            return "-"
        if not done_this_session:
            return "belum bisa diperkirakan"
        secs = (time.time() - self._started) / done_this_session * remaining
        return f"±{secs / 3600:.1f} jam" if secs >= 3600 else f"±{max(1, round(secs / 60))} menit"

    def write_status(self, phase: str, force: bool = False) -> None:
        now = time.time()
        if not force and now - self._last_status < 5:
            return
        self._last_status = now
        done = sum(1 for t in self.tasks if t in self._task_set)
        lines = [
            f"Status scraping : {self.output}",
            f"Diperbarui      : {datetime.now():%Y-%m-%d %H:%M:%S}",
            f"Tahap           : {phase}",
            "",
        ]
        if self.total_tasks:
            pct = done * 100 // self.total_tasks
            lines += [f"Kata kunci x situs selesai : {done} / {self.total_tasks} ({pct}%)"]
            for site in self._sites:
                n_site = sum(1 for kw in self._keywords if (site, kw) in self.tasks)
                lines.append(f"  {site:<13} {n_site} / {len(self._keywords)}")
            n_products = sum(len(v) for t, v in self.tasks.items() if t in self._task_set)
            lines += [f"Produk tersimpan           : {n_products}"]
            if phase == "scraping":
                lines.append(f"Perkiraan sisa scraping    : {self._eta(self.total_tasks - done, self._session_tasks)}")
        if self.failures:
            lines += ["", f"Gagal di jalan ini ({len(self.failures)}), dicoba lagi saat dilanjutkan:"]
            lines += [f"  - {f}" for f in self.failures[-20:]]
        if self.desc_plan:
            lines += ["", "Deskripsi (halaman produk):"]
            for site, total in self.desc_plan.items():
                d = self.desc_done.get(site, 0)
                lines.append(f"  {site:<13} {d} / {total} ({d * 100 // max(total, 1)}%)")
            remaining = sum(self.desc_plan.values()) - sum(self.desc_done.get(s, 0) for s in self.desc_plan)
            if phase == "deskripsi":
                lines.append(f"Perkiraan sisa deskripsi   : {self._eta(remaining, self._session_desc)}")
        lines += [
            "",
            "Untuk melanjutkan bila berhenti, jalankan perintah yang sama:",
            "  " + " ".join(shlex.quote(a) for a in [".venv/bin/python", *sys.argv]),
            "Mulai dari awal: tambahkan --ulang",
        ]
        try:
            self.status_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError as e:
            log.warning("[progres] gagal menulis %s: %s", self.status_path, e)

    def plan(self, sites: list[str], keywords: list[str]) -> None:
        self._sites, self._keywords = sites, keywords
        self._task_set = {(s, k) for s in sites for k in keywords}
        self.total_tasks = len(self._task_set)

    def close(self) -> None:
        self._fh.close()
