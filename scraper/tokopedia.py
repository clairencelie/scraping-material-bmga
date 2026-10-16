"""Tokopedia — memakai endpoint GraphQL publik yang juga dipakai halaman pencarian web."""
from __future__ import annotations

import logging
from urllib.parse import urlencode

import httpx

from .models import Product
from .utils import USER_AGENT, parse_rupiah, polite_sleep, to_float

log = logging.getLogger(__name__)

GQL_URL = "https://gql.tokopedia.com/graphql/SearchProductV5Query"
ROWS_PER_PAGE = 60

QUERY = """
query SearchProductV5Query($params: String!) {
  searchProductV5(params: $params) {
    header { totalData responseCode }
    data {
      products {
        id
        name
        url
        mediaURL { image }
        shop { id name url city tier }
        price { text number original discountPercentage }
        rating
        labelGroups { position title }
      }
    }
  }
}
"""

# Nilai parameter `ob` (urutan) yang dipakai situs Tokopedia.
SORT_OPTIONS = {
    "relevan": 23,
    "termurah": 3,
    "termahal": 4,
    "terbaru": 9,
    "ulasan": 5,
}


def _ribbon_percent(text: str | None) -> float | None:
    """Label pita diskon seperti '38%' -> 38.0."""
    return to_float(text.rstrip("%")) if text and text.endswith("%") else None


class TokopediaScraper:
    name = "tokopedia"

    def __init__(self, sort: str = "relevan") -> None:
        self.sort = SORT_OPTIONS.get(sort, 23)
        self.client = httpx.Client(
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/json",
                "Origin": "https://www.tokopedia.com",
                "Referer": "https://www.tokopedia.com/search",
                "X-Source": "tokopedia-lite",
                "X-Tkpd-Lite-Service": "zeus",
                "X-Device": "desktop-0.0",
            },
            timeout=30,
        )

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.client.close()

    def search(self, keyword: str, max_pages: int = 1) -> list[Product]:
        products: list[Product] = []
        for page in range(1, max_pages + 1):
            params = urlencode(
                {
                    "device": "desktop",
                    "ob": self.sort,
                    "page": page,
                    "q": keyword,
                    "rows": ROWS_PER_PAGE,
                    "safe_search": "false",
                    "scheme": "https",
                    "source": "search",
                    "st": "product",
                    "start": (page - 1) * ROWS_PER_PAGE,
                    "user_id": 0,
                }
            )
            payload = [{"operationName": "SearchProductV5Query", "variables": {"params": params}, "query": QUERY}]
            resp = self.client.post(GQL_URL, json=payload)
            resp.raise_for_status()
            body = resp.json()[0]
            if body.get("errors"):
                raise RuntimeError(f"Tokopedia GraphQL error: {body['errors']}")
            items = body["data"]["searchProductV5"]["data"]["products"] or []
            if not items:
                break
            products.extend(self._to_product(it, keyword) for it in items)
            log.info("[tokopedia] '%s' hal %d: %d produk", keyword, page, len(items))
            if page < max_pages:
                polite_sleep()
        return products

    def _to_product(self, it: dict, keyword: str) -> Product:
        price = it.get("price") or {}
        shop = it.get("shop") or {}
        labels = {lg.get("position"): lg.get("title") for lg in it.get("labelGroups") or []}
        sold = labels.get("ri_product_credibility")
        return Product(
            source=self.name,
            keyword=keyword,
            name=it.get("name", ""),
            price=parse_rupiah(price.get("number")),
            original_price=parse_rupiah(price.get("original")),
            discount_percent=to_float(price.get("discountPercentage")) or _ribbon_percent(labels.get("ri_ribbon")),
            promo=labels.get("promotion_label"),
            # Buang parameter tracking pencarian dari URL produk.
            url=(it.get("url") or "").split("?")[0],
            seller=shop.get("name"),
            location=shop.get("city"),
            rating=to_float(it.get("rating")),
            sold=sold.replace(" terjual", "") if sold else None,
            image=(it.get("mediaURL") or {}).get("image"),
        )
