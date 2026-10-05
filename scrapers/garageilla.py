"""Garageilla (garageilla.com), a Shopify shop: the same JSON route as nautoexpress, car items only.
Its SKUs are mostly internal codes (102003012EG007); a maker-looking SKU is kept as part_no, else a
product code in the title (a battery's TD70R or DIN74L, a filter's DFA570-0)."""

import re
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
        if not scrape.maker_code(offer["part_no"]):
            found = re.search(r"\b[A-Z]{1,5}\d{2,4}[A-Z]?(?:-\d+)?\b", offer["title"])
            offer["part_no"] = found.group(0) if found else None
    return offers, next_url
