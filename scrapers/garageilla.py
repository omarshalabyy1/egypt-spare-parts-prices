"""Garageilla (garageilla.com), a Shopify shop: the same JSON route as nautoexpress, car items only.
Its SKUs are mostly internal codes (102003012EG007); only a maker-looking code is kept as part_no."""

import re
from urllib.parse import quote

from scrapers import nautoexpress

BASE = "https://garageilla.com"
PAGES = [(family, f"{BASE}/collections/{quote(handle)}/products.json?limit=250&page=1") for family, handle in (
    ("filter", "فلاتر"), ("battery", "بطاريات-ملاكي"), ("oil", "special-collection"),
)]


def maker_code(sku):
    """Letters and digits, 4 to 12 long, and not the shop's own digits+EG+digits code."""
    return bool(sku and re.fullmatch(r"(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9]{4,12}", sku)
                and not re.fullmatch(r"\d+EG\d+", sku))


def parse(body, url):
    offers, next_url = nautoexpress.parse(body, url)
    for offer in offers:
        offer["part_no"] = offer["part_no"] if maker_code(offer["part_no"]) else None
    return offers, next_url
