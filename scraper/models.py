from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from datetime import datetime


@dataclass
class Product:
    source: str
    keyword: str
    name: str
    price: int | None
    url: str
    relevant: bool | None = None  # diisi scraper.relevance setelah scraping
    match_score: float | None = None
    original_price: int | None = None
    discount_percent: float | None = None
    promo: str | None = None
    brand: str | None = None
    seller: str | None = None
    location: str | None = None
    rating: float | None = None
    sold: str | None = None
    in_stock: bool | None = None
    image: str | None = None
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def columns(cls) -> list[str]:
        return [f.name for f in fields(cls)]
