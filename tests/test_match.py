"""Checks for the match groups and the generated catalogue, on a small made-up set of offers. No
network and no warehouse are used."""

from decimal import Decimal

import make_catalogue
import tracker


def offer(seller_id, listing_key, price, part_code=None, part_type=None, position=None, car=None, brand=None,
          family="filter"):
    make, model = car.split("-") if car else (None, None)
    return {"seller_id": seller_id, "listing_key": listing_key, "price": Decimal(price), "brand": brand,
            "family": family, "part_type": part_type, "position": position, "car_make": make, "car_model": model,
            "car_key": car, "part_code": part_code}


OFFERS = [
    offer("a", "1", "300", part_code="6PK1460", part_type="belt", family="belt", brand="GATES"),
    offer("b", "1", "320", part_code="6PK1460", part_type="belt", family="belt", brand="GATES"),
    offer("b", "2", "330", part_code="6PK1460", part_type="belt", family="belt", brand="DAYCO"),
    offer("c", "4", "310", part_code="6PK1460", part_type="belt", family="belt"),
    offer("c", "1", "999", part_code="ONLYHERE1", part_type="oil filter", car="hyundai-elantra"),  # one seller
    offer("a", "2", "120", part_type="oil filter", car="hyundai-elantra"),
    offer("b", "3", "140", part_type="oil filter", car="hyundai-elantra"),
    offer("a", "3", "800", part_type="brake pad", position="front", car="kia-cerato", family="brake pad"),
    offer("c", "2", "900", part_type="brake pad", position="front", car="kia-cerato", family="brake pad"),
    offer("b", "4", "700", part_type="brake pad", position="rear", car="kia-cerato", family="brake pad"),
    offer("c", "3", "750", part_type="brake pad", car="kia-cerato", family="brake pad"),  # position unknown
    offer("a", "4", "60", part_type="filter", car="kia-rio"),  # a plain filter: never grouped by type
    offer("b", "5", "65", part_type="filter", car="kia-rio"),
    offer("a", "5", "50", part_type="air filter"),  # no car
    offer("b", "6", "55", part_type="air filter"),
]


def test_match_grades():
    assert tracker.match_groups(OFFERS) == {
        ("a", "1"): ("part_number", "6PK1460"),
        ("b", "1"): ("part_number", "6PK1460"),
        ("b", "2"): ("part_number", "6PK1460"),
        ("c", "4"): ("part_number", "6PK1460"),
        # c/1's code is sold by c alone, so it falls back to its type and car, with a/2 and b/3.
        ("c", "1"): ("type_model", "oil filter|hyundai-elantra"),
        ("a", "2"): ("type_model", "oil filter|hyundai-elantra"),
        ("b", "3"): ("type_model", "oil filter|hyundai-elantra"),
        ("a", "3"): ("type_model", "brake pad|kia-cerato|front"),
        ("c", "2"): ("type_model", "brake pad|kia-cerato|front"),
        # b/4 is the only rear pad, c/3 has no position, a/4 and b/5 are plain filters, a/5 and b/6 name no car.
    }


def test_catalogue_is_the_same_every_time(tmp_path):
    first, second = make_catalogue.catalogue(OFFERS), make_catalogue.catalogue(list(reversed(OFFERS)))
    assert first == second
    make_catalogue.write(first, tmp_path / "one.csv")
    make_catalogue.write(second, tmp_path / "two.csv")
    assert (tmp_path / "one.csv").read_bytes() == (tmp_path / "two.csv").read_bytes()


def test_catalogue_parts():
    parts = {p["match_key"]: p for p in make_catalogue.catalogue(OFFERS)}
    assert set(parts) == {"6PK1460", "oil filter|hyundai-elantra", "brake pad|kia-cerato|front"}
    belt = parts["6PK1460"]
    assert (belt["brand"], belt["family"], belt["name"], belt["match_grade"]) == ("GATES", "belt", "Belt 6PK1460", "part_number")
    assert parts["brake pad|kia-cerato|front"]["name"] == "Brake pad front for Kia Cerato"
    assert parts["oil filter|hyundai-elantra"]["brand"] == "Generic"  # no offer in the group names a brand
    for p in parts.values():
        assert p["part_no"].startswith("EG-") and len(p["part_no"]) == 11
        assert p["our_price"] % Decimal("0.50") == 0
    # The median times a factor from 0.90 to 1.15: belt median 315, oil filter median 140 (of 120, 140, 999).
    assert Decimal("283.50") <= belt["our_price"] <= Decimal("362.50")
    assert Decimal("126") <= parts["oil filter|hyundai-elantra"]["our_price"] <= Decimal("161")
    # The top 20% of 3 groups by offer count, rounded up: the belt, with 4 offers.
    assert [k for k, p in parts.items() if p["is_key"]] == ["6PK1460"]
