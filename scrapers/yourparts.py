"""YourParts (yourparts.com): its public product API, 48 a page (limit=48 is honoured), each page
naming the next. Category ids are the site's leaf categories; the belt leaves are the non-empty ones."""

import json
from decimal import Decimal

API = "https://new-api.yourparts.com/all-products/"
PAGES = [(family, f"{API}?category_id={cid}&limit=48&offset=0&locale=en") for family, cid in (
    ("filter", 654), ("filter", 657), ("brake pad", 643), ("spark plug", 460), ("battery", 501),
    ("bulb", 822), ("oil", 784),
    ("belt", 567), ("belt", 568), ("belt", 569), ("belt", 570), ("belt", 571), ("belt", 573),
)]


def parse(body, url):
    page = json.loads(body)
    offers = []
    for p in page["results"]:
        regular = Decimal(str(p["price"])) if p.get("price") else None
        special = Decimal(str(p["special_price"])) if p.get("special_price") else None
        price = special if special and regular and special < regular else regular
        brand = p.get("brand")
        offers.append({
            "listing_key": str(p["id"]),
            "title": " | ".join(x for x in (p.get("name"), p.get("car_str")) if x),
            "price": price,
            "currency": "EGP",
            "is_discounted": price is not None and price != regular,
            "url": f"https://www.yourparts.com/products/{p['id']}",
            "brand": (brand.get("name") if isinstance(brand, dict) else brand) or None,
            "part_no": None,
            "car_make": p.get("car_str") or None,  # the car the part fits, as the site names it
        })
    return offers, page.get("next")
