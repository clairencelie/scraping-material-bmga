"""Depo Bangunan (Magento) — hasil pencarian dirender di server, cukup parse HTML."""
from __future__ import annotations

import logging

import httpx
from bs4 import BeautifulSoup

from .models import Product
from .utils import USER_AGENT, parse_rupiah, polite_sleep

log = logging.getLogger(__name__)

SEARCH_URL = "https://www.depobangunan.co.id/catalogsearch/result/"


class DepoBangunanScraper:
    name = "depobangunan"

    def __init__(self) -> None:
        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept-Language": "id-ID,id;q=0.9"},
            follow_redirects=True,
            timeout=30,
        )

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.client.close()

    def search(self, keyword: str, max_pages: int = 1) -> list[Product]:
        products: list[Product] = []
        seen: set[str] = set()
        for page in range(1, max_pages + 1):
            resp = self.client.get(SEARCH_URL, params={"q": keyword, "p": page})
            resp.raise_for_status()
            # Magento mengembalikan halaman terakhir lagi bila p melebihi jumlah halaman,
            # jadi berhenti saat tidak ada produk baru.
            page_items = [p for p in self._parse(resp.text, keyword) if p.url not in seen]
            if not page_items:
                break
            seen.update(p.url for p in page_items)
            products.extend(page_items)
            log.info("[depobangunan] '%s' hal %d: %d produk", keyword, page, len(page_items))
            if page < max_pages:
                polite_sleep()
        return products

    def _parse(self, html: str, keyword: str) -> list[Product]:
        soup = BeautifulSoup(html, "html.parser")
        results = []
        for item in soup.select("li.product-item"):
            link = item.select_one("a.product-item-link")
            # Halaman juga berisi satu product-item template tanpa nama.
            if not link or not link.get_text(strip=True):
                continue
            final = item.select_one('[data-price-type="finalPrice"]')
            old = item.select_one('[data-price-type="oldPrice"]')
            price = parse_rupiah(final.get("data-price-amount")) if final else None
            original = parse_rupiah(old.get("data-price-amount")) if old else None
            discount = None
            if price and original and original > price:
                discount = round((original - price) / original * 100, 1)
            sold = item.select_one(".sold-qty-count")
            form = item.select_one("form[data-product-sku]")
            img = item.select_one("img.product-image-photo")
            results.append(
                Product(
                    source=self.name,
                    keyword=keyword,
                    name=link.get_text(strip=True),
                    price=price,
                    original_price=original,
                    discount_percent=discount,
                    url=link.get("href", ""),
                    seller="Depo Bangunan",
                    sold=sold.get_text(strip=True) if sold else None,
                    brand=None,
                    image=img.get("src") if img else None,
                    in_stock=None if form else False,
                )
            )
        return results
