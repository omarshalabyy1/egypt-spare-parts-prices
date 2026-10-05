"""Fit and Fix (fitandfix.com): its Magento GraphQL API, read with GET, 20 products a page."""

import json
import re
from decimal import Decimal
from urllib.parse import parse_qs, urlencode, urlsplit

API = "https://be.fitandfix.com/graphql"
QUERY = ('{products(filter:{category_uid:{eq:"%s"}},pageSize:20,currentPage:%d){total_count items{name sku'
         ' url_key stock_status price_range{maximum_price{final_price{value currency} regular_price{value'
         ' currency}}}} page_info{total_pages current_page}}}')


def page_url(uid, n):
    return f"{API}?{urlencode({'query': QUERY % (uid, n)})}"


PAGES = [(family, page_url(uid, 1)) for family, uid in (
    ("filter", "MjE="), ("brake pad", "MTY2"), ("battery", "NA=="), ("wiper", "MTc="), ("oil", "MjQ="),
)]


def parse(body, url):
    products = json.loads(body)["data"]["products"]
    offers = []
    for p in products["items"]:
        final = p["price_range"]["maximum_price"]["final_price"]
        regular = p["price_range"]["maximum_price"]["regular_price"]
        price = Decimal(str(final["value"])) if final.get("value") else None
        offers.append({
            "listing_key": p["sku"],
            "title": p["name"],
            "price": price,
            "currency": final.get("currency"),
            "is_discounted": bool(price and regular.get("value") and Decimal(str(regular["value"])) > price),
            "url": f"https://www.fitandfix.com/products/{p['url_key']}",
            "brand": None,
            "part_no": None,
        })
    info = products["page_info"]
    uid = re.search(r'category_uid:\{eq:"([^"]+)"\}', parse_qs(urlsplit(url).query)["query"][0]).group(1)
    return offers, page_url(uid, info["current_page"] + 1) if info["current_page"] < info["total_pages"] else None
