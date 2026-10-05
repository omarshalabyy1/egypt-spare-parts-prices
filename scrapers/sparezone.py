"""Spare Zone (sparezone-eg.com): server-rendered HTML, 24 cards a page, prices like '5,175 EGP'."""

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

import scrape

BASE = "https://sparezone-eg.com"
PAGES = [("spark plug", f"{BASE}/brand/spark-plugs"), ("wiper", f"{BASE}/brand/wiper-blade"),
         ("oil", f"{BASE}/brand/oils-fluids")]


def parse(body, url):
    soup = BeautifulSoup(body, "html.parser")
    offers = []
    for card in soup.select(".aiz-card-box"):
        link = card.select_one("h3 a")
        price = card.select_one("div.fs-14 .fw-700")
        price_text = price.get_text(" ", strip=True) if price else ""
        href = urljoin(url, link["href"]) if link and link.get("href") else None
        product_id = re.search(r"showAddToCartModal\((\d+)\)", str(card))  # the site's product id
        offers.append({
            "listing_key": product_id.group(1) if product_id else None,
            "title": (link.get_text(" ", strip=True) or link.get("title")) if link else None,
            "price": scrape.money(price_text),
            "currency": "EGP" if "EGP" in price_text else None,
            "is_discounted": card.select_one("del") is not None,  # the theme's previous price
            "url": href,
            "brand": None,
            "part_no": None,
        })
    following = soup.select_one('a.page-link[rel="next"]')
    return offers, urljoin(url, following["href"]) if following else None
