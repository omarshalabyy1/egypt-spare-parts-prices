"""Checks for the match groups and the generated catalogue, on a small made-up set of offers. No
network and no warehouse are used."""

from decimal import Decimal

import make_catalogue
import tracker


def offer(seller_id, listing_key, price, part_code=None, part_type=None, position=None, car=None, brand=None,
          family="filter", pack="single", in_stock=None, title=None, generation=None, belt_function=None):
    make, model = car.split("-") if car else (None, None)
    return {"seller_id": seller_id, "listing_key": listing_key, "title": title or f"{seller_id}/{listing_key}",
            "price": Decimal(price), "in_stock": in_stock, "brand": brand, "family": family, "part_type": part_type,
            "position": position, "pack": pack, "belt_function": belt_function, "car_make": make, "car_model": model,
            "generation": generation,
            "car_key": car, "part_code": part_code}


PADS = {"part_type": "brake pad", "position": "front", "car": "kia-cerato", "family": "brake pad"}
PLUGS = {"part_type": "spark plug", "car": "kia-rio", "family": "spark plug"}
OFFERS = [
    offer("a", "1", "300", part_code="6PK1460", part_type="belt", family="belt", brand="GATES"),
    offer("b", "1", "320", part_code="6PK1460", part_type="belt", family="belt", brand="GATES"),
    offer("b", "2", "330", part_code="6PK1460", part_type="belt", family="belt", brand="DAYCO"),
    offer("c", "4", "310", part_code="6PK1460", part_type="belt", family="belt"),
    offer("d", "9", "900", part_code="6PK1460", part_type="belt", family="belt", pack="set"),  # a set: not with the singles
    offer("c", "1", "999", part_code="ONLYHERE1", part_type="oil filter", car="hyundai-elantra"),  # one seller's code
    offer("a", "2", "120", part_type="oil filter", car="hyundai-elantra"),
    offer("b", "3", "140", part_type="oil filter", car="hyundai-elantra"),
    offer("a", "3", "800", **PADS),
    offer("c", "2", "900", **PADS),
    offer("b", "8", "700", **PADS, in_stock=False),
    offer("b", "4", "700", **{**PADS, "position": "rear"}),  # the only rear pad
    offer("c", "3", "750", **{**PADS, "position": None}),  # position unknown
    offer("a", "4", "60", part_type="filter", car="kia-rio"),  # a plain filter: never grouped by type
    offer("b", "5", "65", part_type="filter", car="kia-rio"),
    offer("a", "5", "50", part_type="air filter"),  # no car
    offer("b", "6", "55", part_type="air filter"),
    offer("a", "6", "1250", **PLUGS, pack="set"),
    *[offer("d", str(n), "1200", **PLUGS, pack="set") for n in range(1, 6)],  # many offers, two sellers
    offer("b", "7", "300", **PLUGS),  # a single plug: no other seller sells one
]


def members(groups, group):
    return {offer for offer, g in groups.items() if g == group}


def test_match_grades():
    groups = tracker.match_groups(OFFERS)
    assert members(groups, ("part_number", "6PK1460|single")) == {("a", "1"), ("b", "1"), ("b", "2"), ("c", "4")}
    # c/1's code is sold by c alone, so it falls back to its type and car, with a/2 and b/3.
    assert members(groups, ("type_model", "oil filter|hyundai-elantra|single")) == {("c", "1"), ("a", "2"), ("b", "3")}
    assert members(groups, ("type_model", "brake pad|kia-cerato|front|single")) == {("a", "3"), ("c", "2"), ("b", "8")}
    assert members(groups, ("type_model", "spark plug|kia-rio|set")) == {("a", "6"), *(("d", str(n)) for n in range(1, 6))}
    # Not grouped: the belt set (d/9, its seller alone), the rear pad, the pad of unknown position,
    # the plain filters, the air filters naming no car, the single plug.
    assert len(groups) == 4 + 3 + 3 + 6


def test_comparable_is_within_three_times_the_median():
    median = Decimal("140")
    assert tracker.comparable(Decimal("420"), median) and tracker.comparable(Decimal("46.67"), median)
    assert not tracker.comparable(Decimal("420.01"), median) and not tracker.comparable(Decimal("46.66"), median)


def test_catalogue_is_the_same_every_time(tmp_path):
    first, second = make_catalogue.catalogue(OFFERS), make_catalogue.catalogue(list(reversed(OFFERS)))
    assert first == second
    make_catalogue.write(first, tmp_path / "one.csv")
    make_catalogue.write(second, tmp_path / "two.csv")
    assert (tmp_path / "one.csv").read_bytes() == (tmp_path / "two.csv").read_bytes()


def test_catalogue_parts():
    parts = {p["match_key"]: p for p in make_catalogue.catalogue(OFFERS)}
    assert set(parts) == {"6PK1460|single", "oil filter|hyundai-elantra|single", "brake pad|kia-cerato|front|single",
                          "spark plug|kia-rio|set"}
    belt = parts["6PK1460|single"]
    assert (belt["brand"], belt["family"], belt["name"], belt["match_grade"]) == ("GATES", "belt", "Belt 6PK1460", "part_number")
    assert parts["brake pad|kia-cerato|front|single"]["name"] == "Brake pad front for Kia Cerato"
    assert parts["spark plug|kia-rio|set"]["name"] == "Spark plug set for Kia Rio"
    assert parts["oil filter|hyundai-elantra|single"]["brand"] == "Generic"  # no offer in the group names a brand
    assert all(p["part_no"].startswith("EG-") and len(p["part_no"]) == 11 for p in parts.values())
    # Our price is the median of the comparable offers not shown out of stock, to 0.50 EGP:
    assert belt["our_price"] == Decimal("315.00")  # 300, 310, 320, 330
    assert parts["oil filter|hyundai-elantra|single"]["our_price"] == Decimal("130.00")  # 999 is above 3 x 140: left out
    assert parts["brake pad|kia-cerato|front|single"]["our_price"] == Decimal("850.00")  # 700 is out of stock: left out
    assert parts["spark plug|kia-rio|set"]["our_price"] == Decimal("1200.00")
    # The top 20% of 4 groups, rounded up, by sellers: the belt (3 sellers, 4 offers) wins the tie with
    # the oil filter and the pads (3 sellers, 3 offers); the plug set has the most offers but 2 sellers.
    assert [k for k, p in parts.items() if p["is_key"]] == ["6PK1460|single"]


def test_undercut_views_read_the_percent_from_the_database_setting():
    sql = (tracker.ROOT / "sql" / "gold.sql").read_text(encoding="utf-8")
    rule = "their_price <= our_price * (1 - current_setting('client.undercut_pct')::numeric / 100)"
    assert sql.count(rule) == 2 and "0.95" not in sql  # gold.undercut and gold.undercut_alert


def test_generation_splits_type_groups():
    rows = [offer(s, f"{s}{g}", "100", part_type="oil filter", car="nissan-sunny", generation=g)
            for s in ("a", "b") for g in ("N17", "N16", None)]
    assert set(tracker.match_groups(rows).values()) == {
        ("type_model", "oil filter|nissan-sunny-n17|single"), ("type_model", "oil filter|nissan-sunny-n16|single"),
        ("type_model", "oil filter|nissan-sunny|single")}  # naming no generation: compared only with each other


def test_a_repeated_listing_counts_once_in_the_median():
    filters = {"part_type": "oil filter", "car": "kia-rio"}
    rows = [offer("a", str(n), "100", title="Same filter", **filters) for n in range(5)]  # one listing under 5 pages
    rows += [offer("b", "1", "300", **filters), offer("c", "1", "320", **filters)]
    groups = tracker.match_groups(rows)
    assert tracker.group_medians(rows, groups) == {("type_model", "oil filter|kia-rio|single"): Decimal("300")}


def test_a_group_of_fewer_than_three_prices_is_all_comparable():
    rows = [offer("a", "1", "100", part_type="oil filter", car="kia-rio"),
            offer("b", "1", "1000", part_type="oil filter", car="kia-rio")]
    assert tracker.group_medians(rows, tracker.match_groups(rows)) == {}
    assert tracker.comparable(Decimal("1000"), None)


def test_belt_function_splits_type_groups():
    rows = [offer(s, f"{s}{f}", "100", part_type="belt", family="belt", car="kia-cerato", belt_function=f)
            for s in ("a", "b") for f in ("timing", "drive", None)]
    assert set(tracker.match_groups(rows).values()) == {
        ("type_model", "belt|timing|kia-cerato|single"), ("type_model", "belt|drive|kia-cerato|single"),
        ("type_model", "belt|kia-cerato|single")}  # naming no function: compared only with each other
