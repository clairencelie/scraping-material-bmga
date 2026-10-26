from __future__ import annotations

import random
import re
import time

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)


def parse_rupiah(value) -> int | None:
    """'Rp 1.250.000' / 'Rp1,250,000' / 1250000 -> 1250000."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    digits = re.sub(r"[^\d]", "", str(value))
    return int(digits) if digits else None


def to_float(value) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


# Batas isi satu sel Excel adalah 32.767 karakter.
MAX_TEXT = 32_000


def html_to_text(html: str | None) -> str | None:
    """HTML deskripsi -> teks biasa; baris & paragraf dipertahankan, spasi dirapikan."""
    if not html:
        return None
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    # Baris baru hanya di <br> dan elemen blok; tag sebaris (<strong>, <span>) tidak
    # memecah baris, supaya "Produk: Cat Tembok" tetap satu baris.
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for el in soup.find_all(["p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "table", "ul", "ol"]):
        el.insert_after("\n")
    text = soup.get_text()
    lines = [re.sub(r"[ \t\xa0]+", " ", ln).strip() for ln in text.splitlines()]
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return text[:MAX_TEXT] or None


def polite_sleep(min_s: float = 1.5, max_s: float = 3.5) -> None:
    """Jeda acak antar request supaya tidak membebani server."""
    time.sleep(random.uniform(min_s, max_s))
