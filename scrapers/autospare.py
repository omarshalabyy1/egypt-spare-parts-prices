"""AutoSpare (autospare.com.eg): server-rendered HTML, 15 cards a page, prices like '1,850 جنيه'."""

from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

import scrape

BASE = "https://autospare.com.eg"
PAGES = [(family, f"{BASE}/category/{quote(name)}") for family, name in (
    ("filter", "الفلاتر-1"), ("spark plug", "البوجيهات-والمباين"), ("oil", "الزيوت-والسوائل"),
    ("belt", "السيور-والبلي"), ("brake pad", "الفرامل"), ("bulb", "كهرباء-وإضاءة"),
)]


def parse(body, url):
    soup = BeautifulSoup(body, "html.parser")
    offers = []
    for card in soup.select(".noon-card"):
        title = card.select_one("h3.product-title")
        link = card.select_one(".card-info a.text-decoration-none")
        button = card.select_one("button.add-to-card-btn[data-price]")
        shown = card.select_one(".price-container")
        shown_text = shown.get_text(" ", strip=True) if shown else ""
        key = card.select_one("[data-product-id]")
        chip = card.select_one(".card-meta-chip")  # 'المانى - BOSCH': origin - brand; or a category alone
        chip_text = chip.get_text(" ", strip=True) if chip else ""
        offers.append({
            "listing_key": key["data-product-id"] if key else None,
            "title": title.get_text(" ", strip=True) if title else None,
            "price": scrape.money(button["data-price"] if button else shown_text),
            "currency": "EGP" if "جنيه" in shown_text else None,
            "is_discounted": card.select_one(".old-price") is not None,  # the struck-out price
            "url": urljoin(url, link["href"]) if link and link.get("href") else None,
            "brand": (chip_text.rsplit(" - ", 1)[1].strip() or None) if " - " in chip_text else None,
            "part_no": None,
            "in_stock": card.select_one(".out-of-stock-overlay") is None,
        })
    following = soup.select_one('a.page-link[rel="next"]')
    return offers, urljoin(url, following["href"]) if following else None
