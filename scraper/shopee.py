"""Shopee — pencarian hanya bisa dibuka dari browser yang sudah login.

Shopee mengalihkan browser otomatis tanpa sesi ke halaman verifikasi
(`/verify/traffic`). Karena itu scraper ini memakai profil Chromium permanen
(`.browser-profile/shopee`): jalankan `python main.py shopee-login` sekali, login
manual di jendela yang terbuka, lalu scraper memakai sesi yang sama. Data diambil
dari respons API `search_items` yang dipanggil halaman pencarian itu sendiri.
"""
from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import Response, TimeoutError as PWTimeout, sync_playwright

from .models import Product
from .utils import polite_sleep, to_float

log = logging.getLogger(__name__)

PROFILE_DIR = Path(__file__).resolve().parent.parent / ".browser-profile" / "shopee"
SEARCH_PAGE = "https://shopee.co.id/search?keyword={q}&page={page}"
API_MARKER = "/api/v4/search/search_items"
BLOCKED_MARKERS = ("/verify/", "/buyer/login")
PRICE_DIVISOR = 100_000  # Shopee menyimpan harga dalam satuan 1/100000 rupiah.


class ShopeeBlocked(RuntimeError):
    pass


def _launch(pw, headless: bool):
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    return pw.chromium.launch_persistent_context(
        str(PROFILE_DIR),
        headless=headless,
        locale="id-ID",
        viewport={"width": 1366, "height": 900},
        args=["--disable-blink-features=AutomationControlled"],
    )


def interactive_login() -> None:
    """Buka Shopee di jendela browser agar pengguna login sendiri."""
    with sync_playwright() as pw:
        ctx = _launch(pw, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://shopee.co.id/buyer/login")
        input("Login ke Shopee di jendela browser, lalu tekan Enter di sini... ")
        ctx.close()
    print(f"Sesi tersimpan di {PROFILE_DIR}")


class ShopeeScraper:
    name = "shopee"

    def __init__(self, headless: bool = False) -> None:
        # Mode headless jauh lebih sering diblokir Shopee, jadi default-nya tampil.
        self.headless = headless

    def __enter__(self):
        self._pw = sync_playwright().start()
        self._ctx = _launch(self._pw, self.headless)
        self._page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()
        return self

    def __exit__(self, *exc):
        self._ctx.close()
        self._pw.stop()

    def search(self, keyword: str, max_pages: int = 1) -> list[Product]:
        products: list[Product] = []
        for page_no in range(max_pages):
            items = self._fetch_page(keyword, page_no)
            if not items:
                break
            products.extend(self._to_product(it, keyword) for it in items)
            log.info("[shopee] '%s' hal %d: %d produk", keyword, page_no + 1, len(items))
            if page_no < max_pages - 1:
                polite_sleep(3, 6)
        return products

    def _fetch_page(self, keyword: str, page_no: int) -> list[dict]:
        page = self._page
        url = SEARCH_PAGE.format(q=quote(keyword), page=page_no)
        try:
            with page.expect_response(self._is_search_api, timeout=45000) as info:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                # Hasil pencarian baru dimuat setelah halaman di-scroll sedikit.
                page.mouse.wheel(0, 1500)
            data = info.value.json()
        except PWTimeout:
            if any(m in page.url for m in BLOCKED_MARKERS):
                raise ShopeeBlocked(
                    "Shopee meminta login/verifikasi. Jalankan `python main.py shopee-login` "
                    "lalu selesaikan login/verifikasi secara manual di jendela browser."
                ) from None
            raise
        if data.get("error"):
            raise ShopeeBlocked(
                f"API Shopee menolak request (error={data.get('error')}). Biasanya karena belum "
                "login atau sesi terdeteksi sebagai bot; jalankan `python main.py shopee-login`."
            )
        return [it.get("item_basic") or it for it in data.get("items") or []]

    @staticmethod
    def _is_search_api(resp: Response) -> bool:
        return API_MARKER in resp.url and resp.status == 200

    def _to_product(self, it: dict, keyword: str) -> Product:
        def rp(v):
            return int(v) // PRICE_DIVISOR if v else None

        price = rp(it.get("price") or it.get("price_min"))
        original = rp(it.get("price_before_discount"))
        if original and price and original <= price:
            original = None
        shop_id, item_id = it.get("shopid"), it.get("itemid")
        image = it.get("image")
        return Product(
            source=self.name,
            keyword=keyword,
            name=it.get("name", ""),
            price=price,
            original_price=original,
            discount_percent=to_float(it.get("raw_discount")) or None,
            brand=it.get("brand") or None,
            url=f"https://shopee.co.id/product/{shop_id}/{item_id}",
            location=it.get("shop_location"),
            seller=str(it.get("shop_name") or shop_id),
            rating=to_float((it.get("item_rating") or {}).get("rating_star")) or None,
            sold=str(it.get("historical_sold") or it.get("sold") or "") or None,
            in_stock=(it.get("stock") or 0) > 0 if "stock" in it else None,
            image=f"https://down-id.img.susercontent.com/file/{image}" if image else None,
        )
