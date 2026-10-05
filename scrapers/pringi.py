"""Pringi (pringi.com), a WooCommerce shop: the public Store API. Prices come as whole minor units
(15000 with currency_minor_unit 2 = EGP 150.00). A page with no products is the end. The category
filter takes the slug (checked: the slug and the numeric id return the same products)."""

import html
import json
from decimal import Decimal

import scrape

BASE = "https://pringi.com"
# suspension-brakes and electrical-sensors are mixed; their family is a first guess the match step refines.
PAGES = [(family, f"{BASE}/wp-json/wc/store/v1/products?per_page=100&page=1&category={slug}") for family, slug in (
    ("filter", "filters"), ("brake pad", "suspension-brakes"), ("spark plug", "electrical-sensors"),
    ("battery", "battery-tires"), ("belt", "belts-hoses"), ("oil", "engine-oil"),
)]


def parse(body, url):
    products = json.loads(body)
    offers = []
    for p in products:
        prices = p["prices"]
        unit = -int(prices["currency_minor_unit"])
        price = Decimal(prices["price"]).scaleb(unit) if prices.get("price") else None
        regular = Decimal(prices["regular_price"]).scaleb(unit) if prices.get("regular_price") else None
        offers.append({
            "listing_key": str(p["id"]),
            "title": html.unescape(p["name"]),
            "price": price,
            "currency": prices.get("currency_code"),
            "is_discounted": bool(price and regular and regular > price),
            "url": p["permalink"],
            "brand": None,
            "part_no": None,
        })
    return offers, scrape.next_page(url) if products else None
