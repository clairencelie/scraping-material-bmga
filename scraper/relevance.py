"""Penanda apakah nama produk hasil pencarian cocok dengan kata kuncinya.

Pencarian situs (terutama Mitra10) tetap mengembalikan produk lain bila barang yang
dicari tidak dijual, mis. "tabung freon r32" -> mesin cuci 2 tabung. Penanda ini
tidak membuang baris; hanya memberi skor dan label agar bisa disaring.

Aturan: kata kunci dipecah jadi token. Produk dianggap relevan bila
- minimal separuh token ditemukan di nama produk (kata kunci 1-2 token: semua), dan
- semua token spesifikasi (yang mengandung angka: 9mm, 3x2.5, 20x20, 1/2) ditemukan.
Merek pengganti tetap bisa lolos (kabel Supreme untuk kata kunci "eterna"), karena
RAB juga sering menulis "setara".
"""
from __future__ import annotations

import re

# Kata yang menjelaskan satuan jual, bukan barangnya.
IGNORED = {"per", "kubik", "lembar", "meter", "tebal"}
# Ejaan lain yang sering dipakai di nama produk.
SYNONYMS = {
    "kran": {"keran"},
    "kloset": {"closet"},
    "wastafel": {"washtafel", "westafel"},
    "multiplek": {"multipleks", "multiplex", "triplek", "plywood"},
    "spandek": {"spandex", "spandeck"},
    "hollow": {"holo", "hollo"},
    "kompon": {"compound", "coumpound"},
    "aluminium": {"alumunium", "aluminum", "almunium"},
}
# Titik dan "/" hanya menyambung angka (0.5, 1/2), bukan "uk.60x60" atau
# "list/plint/10x60"; "+" menandai pecahan campuran (1+1/2 = 1½) agar tidak
# tertukar dengan 1/2.
TOKEN_RE = re.compile(r"[a-z0-9]+(?:(?:[x+]|(?<=\d)[./](?=\d))[a-z0-9]+)*")


def _normalize(text: str) -> str:
    t = text.lower()
    t = re.sub(r"(\d),(\d)", r"\1.\2", t)  # 0,5 -> 0.5
    t = re.sub(r"(\d)\s*x\s*(\d)", r"\1x\2", t)  # 20 x 20 -> 20x20
    t = re.sub(r"(\d+)[\s-]+(\d+/\d+)", r"\1+\2", t)  # 1 1/2 -> 1+1/2
    t = re.sub(r"(\d)\s*[-:]\s*(\d)", r"\1/\2", t)  # split 1-2 / 1:2 -> 1/2
    t = re.sub(r"(\d)\s*(?:\"|”|'')\s*(?:inch\b|in\b)?", r"\1inch", t)  # 4" / 4" inch -> 4inch
    t = re.sub(r"(\d)\s*(liter|ltr|lt)\b", r"\1l", t)  # 650 liter / 650 L -> 650l
    t = re.sub(r"(\d)\s+(mm|cm|kg|pk|l|inch|w)\b", r"\1\2", t)  # 9 mm -> 9mm
    return t


def _tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(_normalize(text))


def keyword_tokens(keyword: str) -> list[str]:
    toks = [t for t in _tokens(keyword) if t not in IGNORED]
    # Angka pendek lepas ("12" di "12 meter") terlalu umum untuk dicocokkan.
    return [t for t in toks if not (t.isdigit() and len(t) <= 2)]


def score(keyword: str, name: str) -> tuple[float, bool]:
    """(skor 0-1, relevan?) untuk satu pasangan kata kunci & nama produk."""
    wanted = keyword_tokens(keyword)
    if not wanted:
        return 0.0, False
    name_toks = _tokens(name)
    # Untuk merek yang kadang ditulis terpisah ("AQUA PROOF" = aquaproof).
    name_compact = re.sub(r"[^a-z0-9]", "", name.lower())

    def found(tok: str) -> bool:
        variants = {tok} | SYNONYMS.get(tok, set())
        if any(nt.startswith(v) for nt in name_toks for v in variants):
            return True
        return tok.isalpha() and len(tok) >= 6 and tok in name_compact

    hits = {t: found(t) for t in wanted}
    ratio = round(sum(hits.values()) / len(wanted), 2)
    specs_ok = all(ok for t, ok in hits.items() if any(c.isdigit() for c in t))
    # Kata kunci pendek ("pasir beton") terlalu mudah cocok separuh dengan produk lain
    # (mesin bor beton), jadi semua tokennya wajib ada.
    min_ratio = 1.0 if len(wanted) <= 2 else 0.5
    return ratio, ratio >= min_ratio and specs_ok
