"""Run once, for the demo only: generate the made-up retailer's catalogue (data/catalogue.csv) from
the offers in silver. Each match group (tracker.match_groups: a part code two sellers or more sell,
or a part type and car model they do) becomes one of our parts, priced near what the sellers ask.
A real retailer brings its own catalogue instead.

    python make_catalogue.py      # after load_silver; then load_reference loads the file
"""

import csv
import hashlib
import math
import random
import statistics
from collections import Counter, defaultdict
from decimal import ROUND_HALF_UP, Decimal

from psycopg.rows import dict_row

import tracker

SEED = 7  # the same catalogue on every run
FIELDS = ["part_no", "brand", "family", "name", "car_key", "our_price", "is_key", "match_grade", "match_key"]


def most_common(values, default=None):
    """The most frequent non-empty value; a tie goes to the first in sort order."""
    counts = Counter(v for v in values if v)
    return min(counts, key=lambda v: (-counts[v], v)) if counts else default


def our_price(prices, grade, key):
    """The group's median price moved by a factor from 0.90 to 1.15, rounded to 0.50 EGP. The factor
    comes from a generator seeded with the group, so a part keeps its price when other groups change."""
    factor = Decimal(str(random.Random(f"{SEED}|{grade}|{key}").uniform(0.90, 1.15)))
    price = statistics.median(prices) * factor
    return max(Decimal("0.50"), (price * 2).quantize(Decimal("1"), ROUND_HALF_UP) / 2).quantize(Decimal("0.01"))


def name(grade, key, part_type, family, make, model):
    """An English name: 'Belt 6PK1460', 'Brake pad front for Hyundai Elantra'."""
    words = [(part_type or family).capitalize()]
    if grade == "part_number":
        words.append(key)
    elif key.endswith(("|front", "|rear")):
        words.append(key.rsplit("|", 1)[1])
    if make and model:
        words += ["for", make.upper() if make in ("mg", "byd") else make.title(),
                  model.upper() if any(c.isdigit() for c in model) else model.title()]
    return " ".join(words)


def catalogue(offers):
    """One part per match group. offers: seller_id, listing_key, price (the offer's latest), brand,
    family, part_type, position, car_make, car_model, car_key, part_code. The top 20% of groups by
    offer count are key parts."""
    members = defaultdict(list)
    for (seller_id, listing_key), group in tracker.match_groups(offers).items():
        members[group].append((seller_id, listing_key))
    by_offer = {(o["seller_id"], o["listing_key"]): o for o in offers}
    rows = []
    for (grade, key), group in members.items():
        found = [by_offer[o] for o in group]
        car = most_common(o["car_key"] for o in found)
        made = [o for o in found if o["car_key"] == car] or found
        rows.append({
            "part_no": "EG-" + hashlib.sha1(f"{grade}|{key}".encode()).hexdigest()[:8].upper(),
            "brand": most_common((o["brand"] for o in found), "Generic"),
            "family": most_common(o["family"] for o in found),
            "name": name(grade, key, most_common(o["part_type"] for o in found), most_common(o["family"] for o in found),
                         made[0]["car_make"], made[0]["car_model"]),
            "car_key": car,
            "our_price": our_price([o["price"] for o in found], grade, key),
            "match_grade": grade,
            "match_key": key,
            "offers": len(found),
        })
    if len({r["part_no"] for r in rows}) != len(rows):
        raise ValueError("two match groups hash to the same part_no")
    key_parts = {r["part_no"] for r in sorted(rows, key=lambda r: (-r["offers"], r["part_no"]))[:math.ceil(len(rows) * 0.2)]}
    return sorted(({**{k: r[k] for k in FIELDS if k != "is_key"}, "is_key": r["part_no"] in key_parts} for r in rows),
                  key=lambda r: r["part_no"])


def write(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    with tracker.connect() as conn:
        offers = conn.cursor(row_factory=dict_row).execute(
            "SELECT DISTINCT ON (o.seller_id, o.listing_key) o.seller_id, o.listing_key, p.price, o.brand, o.family,"
            " o.part_type, o.position, o.car_make, o.car_model, o.car_key, o.part_code"
            " FROM silver.offer o JOIN silver.price_observation p USING (seller_id, listing_key)"
            " ORDER BY o.seller_id, o.listing_key, p.observed_on DESC").fetchall()
    rows = catalogue(offers)
    write(rows, tracker.ROOT / "data" / "catalogue.csv")
    print(f"data/catalogue.csv: {len(rows)} parts from {len(offers)} offers,"
          f" {sum(r['is_key'] for r in rows)} key parts")
