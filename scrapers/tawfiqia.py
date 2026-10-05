"""Tawfiqia (tawfiqia.com): the category page shows the first 15 products; the rest come through
the site's own "load more" button, a POST to /ar/filterProducts with the page's session cookie and
CSRF token. That POST is named in the cache by a URL carrying its form fields."""

import time
from urllib.parse import parse_qsl, urlencode, urlsplit

from bs4 import BeautifulSoup

import scrape

BASE = "https://tawfiqia.com"
MORE = f"{BASE}/ar/filterProducts"
PER_PAGE = 15  # the page's record_limit
PAGES = [(family, f"{BASE}/ar/shop?category={slug}") for family, slug in (
    ("filter", "filters"), ("belt", "belts"), ("brake pad", "suspension-and-brakes"),  # brakes: mixed
    ("wiper", "wiper-blade"), ("oil", "fluids"), ("battery", "batteries"), ("bulb", "car-lightening"),
)]
_token = None  # the CSRF token of this process's session


def fetch(url, seller_id, run_week):
    global _token
    if not url.startswith(MORE):
        return scrape.fetch(url, seller_id, run_week)
    if _token is None and not scrape.kept(url, seller_id, run_week):
        # A session and its token, from a live shop page (its own page may already be kept).
        page = scrape.http.get(f"{BASE}/ar/shop", timeout=60)
        time.sleep(scrape.MIN_DELAY_S)
        _token = BeautifulSoup(page.content, "html.parser").select_one('meta[name="csrf-token"]')["content"]
    form = dict(parse_qsl(urlsplit(url).query, keep_blank_values=True))
    return scrape.fetch(url, seller_id, run_week, form=form,
                        headers={"X-CSRF-TOKEN": _token or "", "X-Requested-With": "XMLHttpRequest"})


def parse(body, url):
    soup = BeautifulSoup(body, "html.parser")
    offers = []
    for card in soup.select("div.product"):
        link = card.select_one("h2.title a")
        price = card.select_one("div.price")
        price_text = (price.find(string=True, recursive=False) or "").strip() if price else ""
        offers.append({
            "listing_key": link["href"].rstrip("/").rsplit("/", 1)[-1] if link else None,
            "title": link.get_text(" ", strip=True) if link else None,
            "price": scrape.money(price_text),
            "currency": "EGP" if "EGP" in price_text else None,
            "is_discounted": price is not None and price.select_one("del") is not None,
            "url": link["href"] if link else None,
            "brand": None,
            "part_no": None,
        })
    if url.startswith(MORE):  # a load-more answer: another page follows while this one is full
        fields = dict(parse_qsl(urlsplit(url).query, keep_blank_values=True))
        fields["page_number"] = str(int(fields["page_number"]) + 1)
        return offers, f"{MORE}?{urlencode(fields)}" if len(offers) == PER_PAGE else None
    form = soup.select_one("#load_products_form")
    total = soup.select_one("#total_record")
    if not form or not total or int(total["value"]) <= PER_PAGE:
        return offers, None
    # What the button sends: the form's hidden fields (page_number=1, category, load_products).
    fields = {i["name"]: i.get("value", "") for i in form.select('input[type="hidden"][name]')}
    return offers, f"{MORE}?{urlencode(fields)}"
