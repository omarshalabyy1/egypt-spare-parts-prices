"""Garageilla (garageilla.com), a Shopify shop: the same JSON route as nautoexpress, car items only.
Its SKUs are mostly internal codes (102003012EG007); only a maker-looking code is kept as part_no."""

from urllib.parse import quote

import scrape
from scrapers import nautoexpress

BASE = "https://garageilla.com"
PAGES = [(family, f"{BASE}/collections/{quote(handle)}/products.json?limit=250&page=1") for family, handle in (
    ("filter", "فلاتر"), ("battery", "بطاريات-ملاكي"), ("oil", "special-collection"),
)]


def parse(body, url):
    offers, next_url = nautoexpress.parse(body, url)
    for offer in offers:
        offer["part_no"] = offer["part_no"] if scrape.maker_code(offer["part_no"]) else None
    return offers, next_url
