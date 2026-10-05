"""Jumia Egypt (jumia.com.eg): server-rendered HTML, 40 cards a page, prices like 'EGP 1,500.00'.
Its robots.txt permits identified bots under 200 requests a minute. data-ga4-price is never read:
it is not in EGP."""

from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

import scrape

BASE = "https://www.jumia.com.eg"
PAGES = [(family, f"{BASE}/{path}/") for family, path in (
    ("filter", "automobile-replacement-filters"), ("brake pad", "automobile-brake-system-brake-pads"),
    ("battery", "automobile-batteries"), ("belt", "automobile-belts"),
    ("bulb", "automobile-lights-lighting-accessories"), ("oil", "automobile-oils"),
)]


def parse(body, url):
    soup = BeautifulSoup(body, "html.parser")
    offers = []
    for card in soup.select("article.prd"):
        link = card.select_one("a.core")
        title = card.select_one("h3.name")
        price = card.select_one("div.prc")
        price_text = price.get_text(" ", strip=True) if price else ""
        href = urljoin(url, link["href"]) if link and link.get("href") else None
        brand = link.get("data-gtm-brand") if link else None
        offers.append({
            "listing_key": (link.get("data-gtm-id") if link else None) or (urlsplit(href).path if href else None),
            "title": title.get_text(" ", strip=True) if title else None,
            "price": scrape.money(price_text),
            "currency": "EGP" if "EGP" in price_text else None,
            "is_discounted": card.select_one("div.old") is not None,
            "url": href,
            "brand": brand if brand and brand != "Generic" else None,
            "part_no": None,
        })
    following = soup.select_one('link[rel="next"]')
    return offers, urljoin(url, following["href"]) if following else None
