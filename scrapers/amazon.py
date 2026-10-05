"""Amazon Egypt (amazon.eg): its search result pages, one search per family, prices like
'EGP 1,099.00'. A CAPTCHA page stops the run loudly: it is never solved or worked around."""

from urllib.parse import parse_qs, urlencode, urlsplit

from bs4 import BeautifulSoup

import scrape

BASE = "https://www.amazon.eg"


def search(words, page=1):
    return f"{BASE}/s?{urlencode({'k': words, 'page': page, 'language': 'en_AE'})}"


PAGES = [(family, search(words)) for family, words in (
    ("filter", "car oil filter"), ("filter", "car air filter"), ("filter", "car cabin air filter"),
    ("brake pad", "car brake pads"), ("spark plug", "car spark plugs"), ("battery", "car battery"),
    ("belt", "car timing belt"), ("bulb", "car headlight bulb"), ("wiper", "car wiper blades"),
    ("oil", "car engine oil"),
)]


def parse(body, url):
    if b"validateCaptcha" in body or b"api-services-support@amazon.com" in body:
        raise RuntimeError(f"amazon: blocked by bot protection (a CAPTCHA page) at {url}")
    soup = BeautifulSoup(body, "html.parser")
    offers = []
    for card in soup.select('div[data-component-type="s-search-result"][data-asin]'):
        asin = card["data-asin"]
        title = card.select_one("h2")
        price = card.select_one(".a-price:not(.a-text-price) .a-offscreen")
        price_text = price.get_text(strip=True) if price else ""
        offers.append({
            "listing_key": asin,
            "title": title.get_text(" ", strip=True) if title else None,
            "price": scrape.money(price_text),
            "currency": "EGP" if "EGP" in price_text else None,
            "is_discounted": card.select_one(".a-price.a-text-price") is not None,  # a struck-out list price
            "url": f"{BASE}/dp/{asin}",
            "brand": None,
            "part_no": None,
        })
    following = soup.select_one("a.s-pagination-next[href]")
    if not following:
        return offers, None
    # The same search, next page, without the per-visit ids (qid, xpid) and the /-/en/ prefix.
    query = parse_qs(urlsplit(following["href"]).query)
    return offers, search(query["k"][0], int(query["page"][0]))
