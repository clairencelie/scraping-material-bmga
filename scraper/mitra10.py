"""Mitra10 — halaman pencarian memanggil API WizSearch dari browser.

API key WizSearch disisipkan oleh JavaScript situs dan bisa berganti, jadi scraper
membuka halaman pencarian dengan Playwright dan menangkap respons API yang dipanggil
halaman itu sendiri (satu kali buka halaman per nomor halaman).

Harga di hasil pencarian adalah harga dasar katalog. Harga yang dibayar pembeli
berbeda per toko (`vendor_product_data` di GraphQL Mitra10), jadi setelah tiap
halaman scraper mengambil harga toko yang dipilih untuk semua produk sekaligus.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from urllib.parse import quote, urlparse

import httpx
from playwright.sync_api import Response, sync_playwright

from .models import Product
from .utils import MAX_TEXT, USER_AGENT, html_to_text, parse_rupiah, polite_sleep, to_float

log = logging.getLogger(__name__)

SEARCH_PAGE = "https://www.mitra10.com/catalogsearch/result?q={q}"
PRODUCT_PAGE = "https://www.mitra10.com/product/{slug}"
API_MARKER = "wizsearch.in/v1/products/"  # /search untuk hal 1, /filter untuk hal 2+
GRAPHQL_URL = "https://web.mitra10.com/graphql"
DEFAULT_STORE_ID = 18  # MITRA10 Q-BIG, toko yang dipakai situs bila pengunjung belum memilih lokasi

STORES_QUERY = """
{ storeSwitcher(longitude: "", latitude: "") {
    default_vendor_id
    options { vendor_id vendor_name street }
} }
"""
STORE_PRICE_QUERY = """
query ($keys: [String], $store: Int) {
  products(filter: { url_key: { in: $keys } }, pageSize: 100) {
    items {
      url_key
      vendor_product_data(selectedStore: $store) {
        vendor_cost vendor_special_price vendor_stock
        flash_sale_price flash_sale_from flash_sale_to
      }
    }
  }
}
"""


DESCRIPTION_QUERY = """
query ($keys: [String]) {
  products(filter: { url_key: { in: $keys } }, pageSize: 100) {
    items { url_key description { html } short_description { html } }
  }
}
"""
DESCRIPTION_BATCH = 50


def fetch_descriptions(products: list[Product]) -> int:
    """Isi `description` untuk produk Mitra10 sekaligus per 50 produk. Mengembalikan jumlah yang terisi."""
    by_key: dict[str, list[Product]] = {}
    for p in products:
        by_key.setdefault(p.url.rsplit("/", 1)[-1], []).append(p)
    keys = [k for k in by_key if k]
    filled = 0
    with _client() as client:
        for i in range(0, len(keys), DESCRIPTION_BATCH):
            data = _graphql(client, DESCRIPTION_QUERY, {"keys": keys[i:i + DESCRIPTION_BATCH]})
            for item in data["products"]["items"]:
                desc = html_to_text((item.get("description") or {}).get("html"))
                short = html_to_text((item.get("short_description") or {}).get("html"))
                # short_description sering berisi "Keunggulan ..." yang tidak ada di description.
                if short and (not desc or short[:80] not in desc):
                    desc = f"{desc}\n\n{short}" if desc else short
                for p in by_key.get(item["url_key"], []):
                    p.description = desc[:MAX_TEXT] if desc else None
                    filled += bool(desc)
            if i + DESCRIPTION_BATCH < len(keys):
                polite_sleep(1.0, 2.0)
    return filled


def _graphql(client: httpx.Client, query: str, variables: dict | None = None) -> dict:
    params = {"query": query}
    if variables:
        params["variables"] = json.dumps(variables)
    resp = client.get(GRAPHQL_URL, params=params)
    resp.raise_for_status()
    body = resp.json()
    if body.get("errors"):
        raise RuntimeError(f"GraphQL Mitra10 error: {body['errors']}")
    return body["data"]


def _client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT, "Origin": "https://www.mitra10.com", "Referer": "https://www.mitra10.com/"},
        timeout=30,
    )


def list_stores() -> list[dict]:
    """Daftar toko Mitra10: [{vendor_id, vendor_name, street}, ...]."""
    with _client() as c:
        return _graphql(c, STORES_QUERY)["storeSwitcher"]["options"]


def _store_price(v: dict) -> tuple[int | None, int | None]:
    """(harga jual, harga normal) dari vendor_product_data; flash sale dipakai bila sedang berlaku."""
    regular = parse_rupiah(v.get("vendor_cost"))
    price = parse_rupiah(v.get("vendor_special_price")) or regular
    flash = parse_rupiah(v.get("flash_sale_price"))
    if flash and v.get("flash_sale_from") and v.get("flash_sale_to"):
        now = datetime.now().astimezone()
        if datetime.fromisoformat(v["flash_sale_from"]) <= now <= datetime.fromisoformat(v["flash_sale_to"]):
            price = flash
    return price, regular


def _product_url(api_url: str | None) -> str:
    """API memberi URL backend Magento (web.mitra10.com/<slug>.html); halaman produk
    publiknya ada di www.mitra10.com/product/<slug>."""
    slug = urlparse(api_url or "").path.strip("/").removesuffix(".html")
    return PRODUCT_PAGE.format(slug=slug) if slug else ""


def _requested_page(resp: Response) -> int | None:
    req = resp.request
    if API_MARKER not in resp.url or req.method != "POST":
        return None
    try:
        body = json.loads(req.post_data or "{}")
        if "filters" in body:
            body = json.loads(body["filters"])
        return int(body.get("page", 1))
    except (ValueError, TypeError):
        return None


class Mitra10Scraper:
    name = "mitra10"

    def __init__(self, headless: bool = True, store_id: int = DEFAULT_STORE_ID) -> None:
        self.headless = headless
        self.store_id = store_id

    def __enter__(self):
        self._http = _client()
        stores = {s["vendor_id"]: s["vendor_name"] for s in _graphql(self._http, STORES_QUERY)["storeSwitcher"]["options"]}
        if self.store_id not in stores:
            raise ValueError(f"ID toko Mitra10 {self.store_id} tidak ada. Lihat: python main.py mitra10-stores")
        self.store_name = stores[self.store_id]
        log.info("[mitra10] harga diambil dari toko %s (id %d)", self.store_name, self.store_id)
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self.headless)
        self._ctx = self._browser.new_context(locale="id-ID", user_agent=USER_AGENT)
        self._page = self._ctx.new_page()
        return self

    def __exit__(self, *exc):
        self._browser.close()
        self._pw.stop()
        self._http.close()

    def search(self, keyword: str, max_pages: int = 1) -> list[Product]:
        products: list[Product] = []
        seen: set[str] = set()
        total_pages = max_pages
        for page_no in range(1, max_pages + 1):
            if page_no > total_pages:
                break
            payload = self._fetch_page(keyword, page_no)
            total_pages = int(payload.get("pages") or 1)
            items = [it for it in payload.get("result", []) if it.get("id") not in seen]
            if not items:
                break
            seen.update(it.get("id") for it in items)
            page_products = [self._to_product(it, keyword) for it in items]
            self._apply_store_prices(page_products)
            products.extend(page_products)
            log.info("[mitra10] '%s' hal %d/%d: %d produk", keyword, page_no, total_pages, len(items))
            if page_no < min(max_pages, total_pages):
                polite_sleep()
        return products

    def _fetch_page(self, keyword: str, page_no: int) -> dict:
        url = SEARCH_PAGE.format(q=quote(keyword))
        if page_no > 1:
            url += f"&page={page_no}"
        # Halaman bisa memanggil API lebih dari sekali (mis. versi page=1 lalu versi
        # dengan `filters`), jadi tunggu respons yang nomor halamannya cocok.
        with self._page.expect_response(lambda r: _requested_page(r) == page_no, timeout=45000) as info:
            self._page.goto(url, wait_until="domcontentloaded", timeout=60000)
        return info.value.json()["payload"]

    def _apply_store_prices(self, products: list[Product]) -> None:
        by_key = {p.url.rsplit("/", 1)[-1]: p for p in products}
        data = _graphql(self._http, STORE_PRICE_QUERY, {"keys": list(by_key), "store": self.store_id})
        found = 0
        for item in data["products"]["items"]:
            p = by_key.get(item["url_key"])
            vendor = (item.get("vendor_product_data") or [None])[0]
            if not p or not vendor:
                continue
            price, regular = _store_price(vendor)
            if not price:
                continue
            found += 1
            p.price = price
            p.original_price = regular if regular and regular > price else None
            p.discount_percent = round((regular - price) / regular * 100, 1) if p.original_price else None
            p.in_stock = (vendor.get("vendor_stock") or 0) > 0
        if found < len(products):
            log.warning("[mitra10] %d produk tanpa harga toko, memakai harga katalog", len(products) - found)

    def _to_product(self, it: dict, keyword: str) -> Product:
        price = parse_rupiah(it.get("finalPrice")) or parse_rupiah(it.get("sellingPrice"))
        candidates = [parse_rupiah(it.get("sellingPrice")), parse_rupiah(it.get("price"))]
        original = max((c for c in candidates if c), default=None)
        if not original or not price or original <= price:
            original = None
        return Product(
            source=self.name,
            keyword=keyword,
            name=it.get("name", ""),
            price=price,
            original_price=original,
            discount_percent=to_float(it.get("discountPercentage")) or None,
            brand=it.get("brand") or None,
            url=_product_url(it.get("url")),
            seller=self.store_name,
            rating=to_float(it.get("avgRatings")) or None,
            in_stock=it.get("inStock"),
            image=it.get("mainImage"),
        )
