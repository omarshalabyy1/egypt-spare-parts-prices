"""Zait and Filters (zaitandfilters.com): its sitemap lists every product page; the pages whose slug
names one of our families are read, each for its JSON-LD Product (name, sku, mpn, brand, offer).
The site's /api/ is never called. The family comes from the slug, not from PAGES."""

import json
import re
from decimal import Decimal
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup

import scrape

BASE = "https://zaitandfilters.com"
PAGES = [(None, f"{BASE}/sitemap.xml")]
MAX_PAGES = 5000  # the sitemap fans out to about 3,500 product pages
FAMILIES = (("filter", r"فلتر|filter"), ("brake pad", r"تيل|brake-pad|فحمات"), ("spark plug", r"بوج|spark"),
            ("belt", r"(^|-)سير-"), ("wiper", r"مساح|wiper"), ("oil", r"زيت-موتور|engine-oil"))


def family(url):
    """The first family the product slug names (an engine-oil slug naming the sump, كارتير, is not oil)."""
    slug = unquote(urlsplit(url).path).rstrip("/").rsplit("/", 1)[-1]
    for name, pattern in FAMILIES:
        if re.search(pattern, slug, re.I) and not (name == "oil" and "كارتير" in slug):
            return name
    return None


def parse(body, url):
    if url.endswith("sitemap.xml"):
        products = [u for u in re.findall(r"<loc>([^<]+)</loc>", body.decode("utf-8")) if "/products/" in u]
        return [], [u for u in products if family(u)]
    product = None
    for script in BeautifulSoup(body, "html.parser").select('script[type="application/ld+json"]'):
        data = json.loads(script.string or "null")
        for item in data if isinstance(data, list) else (data or {}).get("@graph", [data]):
            if isinstance(item, dict) and item.get("@type") == "Product":
                product = item
    if product is None:
        return [], None
    offer = product.get("offers") or {}
    offer = offer[0] if isinstance(offer, list) else offer
    sku, mpn = product.get("sku"), product.get("mpn")
    return [{
        "listing_key": urlsplit(url).path,
        "title": product.get("name"),
        "price": Decimal(str(offer["price"])) if offer.get("price") not in (None, "") else None,
        "currency": offer.get("priceCurrency"),
        "is_discounted": False,  # JSON-LD carries no previous price
        "url": url,
        "brand": (product.get("brand") or {}).get("name"),
        "part_no": scrape.part_code(mpn) if mpn and mpn != sku else None,  # mpn equal to the shop's sku is not a maker code
        "in_stock": {"InStock": True, "OutOfStock": False}.get(str(offer.get("availability", "")).rsplit("/", 1)[-1]),
        "family": family(url),
    }], None
