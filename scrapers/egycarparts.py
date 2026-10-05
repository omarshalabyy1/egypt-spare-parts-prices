"""Egy Car Parts (egycarparts.com), a Shopify shop: the same JSON route and fields as nautoexpress.
Prices are EGP (the shop's /meta.json says currency EGP). Handles picked from its /collections.json
on 2026-10-05, with that day's products_count."""

from scrapers.nautoexpress import parse  # noqa: F401  (the same Shopify JSON)

BASE = "https://egycarparts.com"
PAGES = [(family, f"{BASE}/collections/{handle}/products.json?limit=250&page=1") for family, handle in (
    ("filter", "oil-filter"),             # 729
    ("filter", "air-filters"),            # 512
    ("filter", "evaporation-filters"),    # 363, cabin (air conditioning) filters
    ("filter", "fuel-filters"),           # 158
    ("filter", "other-filters"),          # 32
    ("brake pad", "brake-pads"),          # 1,062
    ("spark plug", "spark-plugs"),        # 508
    ("battery", "car-battery"),           # 53
    ("belt", "car-drive-belt"),           # 166
    ("belt", "timing-belts"),             # 133
    ("bulb", "car-bulbs"),                # 22
    ("wiper", "wiper-blades"),            # 108
    ("oil", "engine-oils"),               # 20
)]
