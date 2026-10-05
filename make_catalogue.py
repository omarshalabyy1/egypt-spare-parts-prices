"""Run once, for the demo only: generate the made-up retailer's catalogue (data/input/catalogue.csv) from
the offers in silver. Each match group (tracker.match_groups: a part code two sellers or more sell,
or a part type and car model they do, split into sets and single pieces) becomes one of our parts,
priced at the market's median. A real retailer brings its own catalogue instead.

    python make_catalogue.py      # after load_silver; then load_reference loads the file
"""

import csv
import hashlib
import math
from collections import Counter, defaultdict
from decimal import ROUND_HALF_UP, Decimal

from psycopg.rows import dict_row

import tracker

FIELDS = ["part_no", "brand", "family", "name", "car_key", "our_price", "is_key", "match_grade", "match_key"]


def most_common(values, default=None):
    """The most frequent non-empty value; a tie goes to the first in sort order."""
    counts = Counter(v for v in values if v)
    return min(counts, key=lambda v: (-counts[v], v)) if counts else default


def our_price(found, median):
    """The median price of the group's comparable offers not shown out of stock (all comparable
    offers if every one is out of stock), each (seller, title, price) once, rounded to 0.50 EGP."""
    usable = [o for o in found if tracker.comparable(o["price"], median)]
    price = tracker.median_price([o for o in usable if o["in_stock"] is not False] or usable)
    return max(Decimal("0.50"), (price * 2).quantize(Decimal("1"), ROUND_HALF_UP) / 2).quantize(Decimal("0.01"))


def name(grade, key, part_type, family, make, model):
    """An English name: 'Belt 6PK1460', 'Brake pad front set for Hyundai Elantra'."""
    fields = key.split("|")
    words = [(part_type or family).capitalize()]
    if grade == "part_number":
        words.append(fields[0])
    elif fields[-2] in ("front", "rear"):
        words.append(fields[-2])
    elif fields[1] in ("timing", "drive"):  # a belt's function: 'Belt timing for Kia Cerato'
        words.append(fields[1])
    if fields[-1] == "set":
        words.append("set")
    if make and model:
        words += ["for", make.upper() if make in ("mg", "byd") else make.title(),
                  model.upper() if any(c.isdigit() for c in model) else model.title()]
    return " ".join(words)


def catalogue(offers):
    """One part per match group. offers: seller_id, listing_key, title, price (the offer's latest),
    in_stock, brand, family, part_type, position, pack, belt_function, car_make, car_model, generation,
    car_key, part_code. The top 20% of
    groups by number of sellers (ties by number of offers) are key parts."""
    groups = tracker.match_groups(offers)
    medians = tracker.group_medians(offers, groups)
    members = defaultdict(list)
    for o in offers:
        group = groups.get((o["seller_id"], o["listing_key"]))
        if group:
            members[group].append(o)
    rows = []
    for (grade, key), found in members.items():
        car = most_common(o["car_key"] for o in found)
        made = [o for o in found if o["car_key"] == car] or found
        rows.append({
            "part_no": "EG-" + hashlib.sha1(f"{grade}|{key}".encode()).hexdigest()[:8].upper(),
            "brand": most_common((o["brand"] for o in found), "Generic"),
            "family": most_common(o["family"] for o in found),
            "name": name(grade, key, most_common(o["part_type"] for o in found), most_common(o["family"] for o in found),
                         made[0]["car_make"], made[0]["car_model"]),
            "car_key": car,
            "our_price": our_price(found, medians.get((grade, key))),
            "match_grade": grade,
            "match_key": key,
            "sellers": len({o["seller_id"] for o in found}),
            "offers": len(found),
        })
    if len({r["part_no"] for r in rows}) != len(rows):
        raise ValueError("two match groups hash to the same part_no")
    ranked = sorted(rows, key=lambda r: (-r["sellers"], -r["offers"], r["part_no"]))
    key_parts = {r["part_no"] for r in ranked[:math.ceil(len(rows) * 0.2)]}
    return sorted(({**{k: r[k] for k in FIELDS if k != "is_key"}, "is_key": r["part_no"] in key_parts} for r in rows),
                  key=lambda r: r["part_no"])


def write(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    with tracker.connect() as conn:
        offers = conn.cursor(row_factory=dict_row).execute(tracker.LATEST_OFFERS).fetchall()
    rows = catalogue(offers)
    write(rows, tracker.CONFIG["input_dir"] / tracker.CONFIG["inputs"]["catalogue"])
    print(f"data/input/{tracker.CONFIG['inputs']['catalogue']}: {len(rows)} parts from {len(offers)} offers,"
          f" {sum(r['is_key'] for r in rows)} key parts")
