"""Checks for the site parsers, each against one real listing page kept under tests/pages/ (fetched
2026-10-05), and for walking the kept pages. No network and no warehouse are used."""

import csv
import gzip
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

import scrape
import tracker
from scrapers import autospare, garageilla, nautoexpress, pringi, sparezone

PAGES = Path(__file__).parent / "pages"
FAMILIES = {"filter", "brake pad", "spark plug", "battery", "belt", "bulb", "wiper", "oil"}


def page(name):
    return (PAGES / name).read_bytes()


def by_key(offers):
    return {o["listing_key"]: o for o in offers}


def test_every_seller_has_a_scraper_and_known_families():
    with open(tracker.ROOT / "data" / "sellers.csv", newline="", encoding="utf-8") as f:
        assert {r["seller_id"] for r in csv.DictReader(f)} == set(tracker.SCRAPERS)
    for scraper in tracker.SCRAPERS.values():
        assert {family for family, url in scraper.PAGES} <= FAMILIES


def test_week_of_is_the_monday():
    assert tracker.week_of(date(2026, 10, 5)) == date(2026, 10, 5)
    assert tracker.week_of(date(2026, 10, 11)) == date(2026, 10, 5)


def test_nautoexpress():
    url = "https://nautoexpress.com/collections/engine-oil/products.json?limit=250&page=1"
    offers, next_url = nautoexpress.parse(page("nautoexpress.json"), url)
    assert len(offers) == 11 and all(scrape.check(o) is None for o in offers)
    first = by_key(offers)["7980830949539"]
    assert (first["title"], first["price"], first["brand"], first["part_no"], first["is_discounted"]) == (
        "Automatic Transmission Oil 1 Liter For Peugeot - Citroen", Decimal("1338.36"), "PSA GROUP", "P9730AE", False)
    assert by_key(offers)["9238897164451"]["is_discounted"]  # 3111.06, was 3274.08
    assert next_url == url.replace("page=1", "page=2")
    assert nautoexpress.parse(b'{"products": []}', next_url) == ([], None)


def test_garageilla_keeps_only_maker_codes():
    url = garageilla.PAGES[-1][1]
    offers, next_url = garageilla.parse(page("garageilla.json"), url)
    assert len(offers) == 25 and all(scrape.check(o) is None for o in offers)
    first = by_key(offers)["9831703249191"]
    assert (first["price"], first["brand"], first["part_no"]) == (Decimal("810.00"), "التعاون", None)
    assert next_url.endswith("page=2") and garageilla.parse(b'{"products": []}', next_url) == ([], None)
    assert [garageilla.maker_code(s) for s in ("OC90", "HX515W50", "29934", "1020EG07", "102003012EG007", None)] == [
        True, True, False, False, False, False]


def test_pringi():
    url = pringi.PAGES[-1][1]
    offers, next_url = pringi.parse(page("pringi.json"), url)
    assert len(offers) == 2 and all(scrape.check(o) is None for o in offers)
    first = by_key(offers)["59814"]
    assert (first["title"], first["price"], first["is_discounted"], first["url"]) == (
        "زيت فرامل 450 مللى Valeo – DOT4", Decimal("191.00"), True, "https://pringi.com/product/765292065/")
    assert next_url == "https://pringi.com/wp-json/wc/store/v1/products?per_page=100&page=2&category=engine-oil"
    assert pringi.parse(b"[]", next_url) == ([], None)


def test_sparezone():
    url = sparezone.PAGES[0][1]
    offers, next_url = sparezone.parse(page("sparezone.html"), url)
    assert len(offers) == 24 and all(scrape.check(o) is None for o in offers)
    assert by_key(offers)["/product/bogyhat-mg-sayk"]["price"] == Decimal("990")
    assert by_key(offers)["/product/mbrd-ftys-bmw-f25-fyby"]["price"] == Decimal("5175")
    assert next_url == "https://sparezone-eg.com/brand/spark-plugs?page=2"
    # A last page: the same page without its next link (a modified copy, not a real last page).
    assert sparezone.parse(page("sparezone.html").replace(b'rel="next"', b""), url)[1] is None


def test_autospare():
    url = autospare.PAGES[1][1] + "?page=59"  # a real page kept by the 2026-10-05 run
    offers, next_url = autospare.parse(page("autospare.html"), url)
    assert len(offers) == 15 and all(scrape.check(o) is None for o in offers)
    assert by_key(offers)["11855"]["title"] == "طقم بوجيهات دابل اريديوم سكودا اوكتافيا A7"
    assert by_key(offers)["11855"]["price"] == Decimal("2000")
    assert [o["listing_key"] for o in offers if o["is_discounted"]] == ["11623"]  # 2950, struck-out price shown
    assert next_url == autospare.PAGES[1][1] + "?page=60"
    # A last page: the same page without its next link (a modified copy, not a real last page).
    assert autospare.parse(page("autospare.html").replace(b'rel="next"', b""), url)[1] is None


# --- Walking the kept pages ------------------------------------------------------------------------

URL = "https://pringi.com/wp-json/wc/store/v1/products?per_page=100&page=1&category=engine-oil"
URL2 = "https://pringi.com/wp-json/wc/store/v1/products?per_page=100&page=2&category=engine-oil"


def keep(root, pages):
    """Write pages ({url: body}) as fetch would have kept them for test-seller, fetched 2026-10-05."""
    folder = root / "data" / "raw" / "test-seller" / "2026-10-05"
    folder.mkdir(parents=True)
    with open(folder / "index.jsonl", "w", encoding="utf-8") as index:
        for n, (url, body) in enumerate(pages.items()):
            path = folder / f"{n}.json.gz"
            path.write_bytes(gzip.compress(body))
            index.write(json.dumps({"url": url, "path": path.relative_to(root).as_posix(),
                                    "fetched_at": "2026-10-05T23:59:00+00:00", "status": 200}) + "\n")


@pytest.fixture
def seller(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "ROOT", tmp_path)
    monkeypatch.setitem(tracker.SCRAPERS, "test-seller", SimpleNamespace(PAGES=[("oil", URL)], parse=pringi.parse))
    return tmp_path


def test_offers_carry_family_and_the_fetch_day(seller):
    keep(seller, {URL: page("pringi.json"), URL2: b"[]"})
    rows = tracker.offers("test-seller", "2026-10-05")
    assert len(rows) == 2
    assert {(r["family"], r["observed_on"], r["fetched_at"]) for r in rows} == {
        ("oil", date(2026, 10, 5), "2026-10-05T23:59:00+00:00")}


def test_empty_parse_of_kept_pages_fails_loudly(seller):
    keep(seller, {URL: b"[]"})
    with pytest.raises(ValueError, match="parsed to no offers"):
        tracker.offers("test-seller", "2026-10-05")


def test_missing_kept_page_fails_loudly(seller):
    keep(seller, {URL: page("pringi.json")})  # page 2 was never kept
    with pytest.raises(RuntimeError, match="not among the kept pages"):
        tracker.offers("test-seller", "2026-10-05")


def test_fetch_follows_next_links_and_fails_on_a_missing_page(seller, monkeypatch):
    calls = []
    monkeypatch.setattr(scrape, "fetch", lambda url, s, w: calls.append(url) or (page("pringi.json") if url == URL else None))
    with pytest.raises(RuntimeError, match="1 listing page"):
        tracker.fetch_pages("test-seller", "2026-10-05")
    assert calls == [URL, URL2]


def test_fetch_stops_at_the_page_cap(seller, monkeypatch, capsys):
    monkeypatch.setitem(tracker.SCRAPERS, "test-seller",
                        SimpleNamespace(PAGES=[("oil", URL)], parse=lambda body, url: ([], url + "x")))
    calls = []
    monkeypatch.setattr(scrape, "fetch", lambda url, s, w: calls.append(url) or b"[]")
    tracker.fetch_pages("test-seller", "2026-10-05")
    assert len(calls) == tracker.MAX_PAGES and "page cap" in capsys.readouterr().out
