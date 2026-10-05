"""N Auto Express (nautoexpress.com), a Shopify shop: the public JSON route of each collection.
Prices are EGP (the shop's /meta.json says currency EGP); a page with no products is the end."""

import json
from decimal import Decimal
from urllib.parse import quote, urlsplit

import scrape

BASE = "https://nautoexpress.com"
PAGES = [(family, f"{BASE}/collections/{handle}/products.json?limit=250&page=1") for family, handle in (
    ("filter", "engine-oil-filters"), ("filter", "air-filters"), ("filter", "air-condition-filters"),
    ("filter", "fuel-filters"), ("brake pad", "brake-pads"), ("spark plug", "spark-plugs"),
    ("battery", "battery"), ("belt", "belts-tensioners-pulleys"), ("bulb", "lighting"),
    ("wiper", "wipers-blades"), ("oil", "engine-oil"),
)]


def parse(body, url):
    products = json.loads(body)["products"]
    base = urlsplit(url)._replace(path="", query="").geturl()
    offers = []
    for p in products:
        variant = p["variants"][0]
        price = Decimal(variant["price"]) if variant.get("price") else None
        was = Decimal(variant["compare_at_price"]) if variant.get("compare_at_price") else None
        offers.append({
            "listing_key": str(p["id"]),
            "title": p["title"],
            "price": price,
            "currency": "EGP",
            "is_discounted": bool(price and was and was > price),
            "url": f"{base}/products/{quote(p['handle'])}",
            "brand": (p.get("vendor") or "").strip() or None,
            "part_no": scrape.part_code(variant.get("sku")),
            "in_stock": variant.get("available"),
        })
    return offers, scrape.next_page(url) if products else None
