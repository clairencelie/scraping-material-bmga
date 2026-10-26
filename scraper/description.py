"""Mengisi kolom `description` (deskripsi produk dari halaman produk).

Deskripsi tidak ada di hasil pencarian, jadi harus diambil per produk:
- Mitra10: GraphQL, 50 produk per request -> semua produk diambil.
- Depo Bangunan & Tokopedia: satu halaman produk per request -> hanya produk yang
  `relevant`, maksimal `max_per_keyword` per (situs, kata kunci), urut hasil pencarian.
- Shopee: belum didukung.
URL yang sama hanya diambil sekali. Server Tokopedia lambat (±4,5 dtk per halaman),
jadi halamannya diambil oleh 3 pekerja paralel; tiap pekerja tetap berjeda 1-2 dtk.
"""
from __future__ import annotations

import logging
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import httpx

from . import depobangunan, mitra10, tokopedia
from .models import Product
from .utils import USER_AGENT, polite_sleep

log = logging.getLogger(__name__)

PER_PAGE_FETCHERS = {
    "depobangunan": depobangunan.fetch_description,
    "tokopedia": tokopedia.fetch_description,
}
# Jumlah halaman produk yang diambil bersamaan per situs.
WORKERS = {"depobangunan": 1, "tokopedia": 3}
# Berhenti mengambil dari satu situs bila gagal berturut-turut sebanyak ini (mis. diblokir).
MAX_CONSECUTIVE_FAILURES = 10


def _pick(products: list[Product], max_per_keyword: int, only_relevant: bool) -> list[Product]:
    taken: dict[tuple[str, str], int] = defaultdict(int)
    picked = []
    for p in products:
        if p.description or (only_relevant and not p.relevant):
            continue
        key = (p.source, p.keyword)
        if max_per_keyword and taken[key] >= max_per_keyword:
            continue
        taken[key] += 1
        picked.append(p)
    return picked


def enrich(products: list[Product], max_per_keyword: int = 10, only_relevant: bool = True) -> None:
    """Isi `description` di tempat. `max_per_keyword=0` = tanpa batas."""
    mitra = [p for p in products if p.source == "mitra10" and not p.description]
    if mitra:
        log.info("[deskripsi] mitra10: %d produk (GraphQL per 50)", len(mitra))
        try:
            n = mitra10.fetch_descriptions(mitra)
            log.info("[deskripsi] mitra10: %d terisi", n)
        except Exception as e:
            log.error("[deskripsi] mitra10 gagal: %s", e)

    if any(p.source == "shopee" for p in products):
        log.warning("[deskripsi] shopee belum didukung, kolom description dibiarkan kosong")

    for site, fetch in PER_PAGE_FETCHERS.items():
        targets = _pick([p for p in products if p.source == site], max_per_keyword, only_relevant)
        urls = list(dict.fromkeys(p.url for p in targets if p.url))
        if not urls:
            continue
        log.info("[deskripsi] %s: %d halaman produk", site, len(urls))
        cache = _fetch_all(site, fetch, urls)
        for p in targets:
            if cache.get(p.url):
                p.description = cache[p.url]
        log.info("[deskripsi] %s: %d terisi", site, sum(1 for v in cache.values() if v))


def _fetch_all(site: str, fetch, urls: list[str]) -> dict[str, str | None]:
    cache: dict[str, str | None] = {}
    lock = threading.Lock()
    stop = threading.Event()
    state = {"done": 0, "failures": 0}

    with httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=30) as client:
        def work(url: str) -> None:
            if stop.is_set():
                return
            try:
                text = fetch(client, url)
                ok = True
            except Exception as e:
                text, ok = None, False
                log.warning("[deskripsi] %s gagal (%s): %s", site, e.__class__.__name__, url)
            with lock:
                cache[url] = text
                state["done"] += 1
                state["failures"] = 0 if ok else state["failures"] + 1
                if state["failures"] >= MAX_CONSECUTIVE_FAILURES and not stop.is_set():
                    log.error("[deskripsi] %s: %d kali gagal berturut-turut, berhenti", site, state["failures"])
                    stop.set()
                if state["done"] % 50 == 0:
                    log.info("[deskripsi] %s: %d/%d", site, state["done"], len(urls))
            polite_sleep(1.0, 2.0)

        with ThreadPoolExecutor(max_workers=WORKERS.get(site, 1)) as pool:
            list(pool.map(work, urls))
    return cache
