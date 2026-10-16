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


def polite_sleep(min_s: float = 1.5, max_s: float = 3.5) -> None:
    """Jeda acak antar request supaya tidak membebani server."""
    time.sleep(random.uniform(min_s, max_s))
