"""GE Trading (getradingeg.com), an Odoo shop: server-rendered HTML, 20 cards a page. A card with no
price shown is kept with price None, so the check sends it to quarantine ("no price shown")."""

import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

import scrape

BASE = "https://www.getradingeg.com"
PAGES = [(family, f"{BASE}/shop/category/{slug}") for family, slug in (
    ("filter", "maintenance-products-oil-filters-20"), ("filter", "maintenance-products-air-filters-24"),
    ("filter", "maintenance-products-fuel-filters-21"), ("filter", "maintenance-products-a-c-filters-25"),
    ("brake pad", "brake-parts-brake-pads-shoes-27"), ("spark plug", "maintenance-products-spark-plugs-4"),
    ("battery", "electrical-parts-batteries-69"), ("belt", "maintenance-products-belts-tensioners-13"),
    ("bulb", "electrical-parts-lamps-16"), ("wiper", "body-parts-wiper-blades-29"),
    ("oil", "maintenance-products-automotive-oils-7"),
)]


def part_no(title):
    """The code in the title's last brackets, e.g. 'Spark Plug ... (SP1047)' -> 'SP1047'."""
    found = re.search(r"\(([^()]+)\)\s*$", title or "")
    return found.group(1).strip() if found and not found.group(1).lower().startswith("made in") else None


def parse(body, url):
    soup = BeautifulSoup(body, "html.parser")
    offers = []
    for card in soup.select("form.oe_product_cart"):
        link = card.select_one("h2.o_wsale_products_item_title a")
        title = card.select_one("h2.o_wsale_products_item_title a span")
        price = card.select_one(".product_price .oe_currency_value")
        href = urljoin(url, link["href"]) if link and link.get("href") else None
        name = title.get_text(" ", strip=True) if title else None
        offers.append({
            "listing_key": urlsplit(href).path if href else None,
            "title": name,
            "price": scrape.money(price.get_text(strip=True)) if price else None,
            "currency": "EGP",  # shown as E£
            "is_discounted": card.select_one(".product_price del") is not None,
            "url": href,
            "brand": None,
            "part_no": part_no(name),
        })
    pages = soup.select_one("ul.pagination")
    last = pages.select("li")[-1] if pages else None  # the "next" arrow, disabled on the last page
    following = last.select_one("a[href]") if last and "disabled" not in last.get("class", []) else None
    return offers, urljoin(url, following["href"]) if following else None
