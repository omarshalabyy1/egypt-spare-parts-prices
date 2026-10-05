"""Checks for the fetcher, the schema check and saving: run with `pytest`. No network is used; the
save test runs only when the warehouse is reachable (WAREHOUSE_PASSWORD set) and rolls back."""

import gzip
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from urllib.robotparser import RobotFileParser

import psycopg
import pytest

import scrape
import tracker

URL = "https://shop.example/p/oil-filter-0761"
WEEK = date(2026, 10, 5)
GOOD = {"seller_id": "test-seller", "listing_key": URL, "family": "filter", "title": "Oil filter 0761", "brand": "Bosch",
        "part_no": "0761", "url": URL, "price": Decimal("350.25"), "currency": "EGP", "is_discounted": False,
        "observed_on": WEEK, "fetched_at": datetime(2026, 10, 5, 9, 0, tzinfo=timezone.utc)}


class Response:
    def __init__(self, status_code, content=b""):
        self.status_code, self.content = status_code, content
        self.ok, self.text = status_code < 400, content.decode()


@pytest.fixture
def offline(tmp_path, monkeypatch):
    """data/raw under a temp folder, robots.txt allowing all, no sleeping, and http.get answering
    from the list the test puts in calls[]."""
    rules = RobotFileParser()
    rules.parse([])
    answers, calls, sleeps = [], [], []
    monkeypatch.setattr(scrape, "ROOT", tmp_path)
    monkeypatch.setattr(scrape, "robots", lambda url: rules)
    monkeypatch.setattr(scrape.time, "sleep", sleeps.append)
    monkeypatch.setattr(scrape.http, "get", lambda url, timeout: calls.append(url) or answers.pop(0))
    return tmp_path, answers, calls, sleeps


def test_good_row_passes():
    assert scrape.check(GOOD) is None


@pytest.mark.parametrize("change, reason", [
    ({"title": " "}, "title missing"),
    ({"url": "ftp://shop.example/p/1"}, "url not http(s)"),
    ({"price": 350.25}, "price not a Decimal between 0 and 1,000,000"),
    ({"price": Decimal("0")}, "price not a Decimal between 0 and 1,000,000"),
    ({"currency": "USD"}, "currency not EGP"),
    ({"listing_key": ""}, "listing_key missing"),
])
def test_bad_rows_have_reasons(change, reason):
    assert scrape.check({**GOOD, **change}) == reason


def test_cached_page_is_read_not_fetched_and_not_slept_on(offline):
    root, answers, calls, sleeps = offline
    folder = root / "data" / "raw" / "test-seller" / str(WEEK)
    folder.mkdir(parents=True)
    (folder / f"{scrape.hashlib.sha1(URL.encode()).hexdigest()[:12]}.html.gz").write_bytes(
        gzip.compress(b"<html>kept</html>"))
    assert scrape.fetch(URL, "test-seller", WEEK) == b"<html>kept</html>"
    assert calls == [] and sleeps == []


def test_live_page_is_kept_gzipped_then_read_from_disk(offline):
    root, answers, calls, sleeps = offline
    answers += [Response(503), Response(200, b"<html>live</html>")]
    assert scrape.fetch(URL, "test-seller", WEEK) == b"<html>live</html>"
    assert scrape.fetch(URL, "test-seller", WEEK) == b"<html>live</html>"
    assert len(calls) == 2  # one retry after the 503, then the second fetch came from disk
    assert sleeps == [3, 2, 3]  # the pace after each live request and the backoff; none for the disk read
    [line] = (root / "data" / "raw" / "test-seller" / str(WEEK) / "index.jsonl").read_text().splitlines()
    assert json.loads(line)["status"] == 200 and json.loads(line)["path"].endswith(".html.gz")


def test_json_page_is_kept_as_json(offline):
    root, answers, calls, sleeps = offline
    answers.append(Response(200, b'{"products": []}'))
    scrape.fetch(URL, "test-seller", WEEK)
    [kept] = (root / "data" / "raw" / "test-seller" / str(WEEK)).glob("*.gz")
    assert kept.name.endswith(".json.gz") and gzip.decompress(kept.read_bytes()) == b'{"products": []}'


@pytest.mark.parametrize("status, allowed", [(200, True), (404, True), (403, False), (503, False)])
def test_robots_txt_status(status, allowed, monkeypatch):
    """No robots.txt (404) allows all; a locked one (401/403) or a server error (5xx) allows nothing."""
    monkeypatch.setattr(scrape, "_robots", {})
    monkeypatch.setattr(scrape.time, "sleep", lambda s: None)
    monkeypatch.setattr(scrape.http, "get", lambda url, timeout: Response(status, b"User-agent: *\nAllow: /\n"))
    assert scrape.allowed(URL) is allowed


@pytest.mark.parametrize("text, value", [("EGP 1,500.00", Decimal("1500.00")), ("990 EGP", Decimal("990")),
                                         ("1,850 جنيه", Decimal("1850")), ("EGP 100 - EGP 200", None), ("", None)])
def test_money(text, value):
    assert scrape.money(text) == value


def test_not_found_is_recorded_and_returns_none(offline):
    root, answers, calls, sleeps = offline
    answers.append(Response(404))
    assert scrape.fetch(URL, "test-seller", WEEK) is None
    [line] = (root / "data" / "raw" / "test-seller" / str(WEEK) / "index.jsonl").read_text().splitlines()
    assert json.loads(line)["status"] == 404 and json.loads(line)["path"] is None


def test_server_down_fails_loudly(offline):
    root, answers, calls, sleeps = offline
    answers += [Response(500)] * 4
    with pytest.raises(RuntimeError, match="no answer after 4 tries"):
        scrape.fetch(URL, "test-seller", WEEK)


def test_empty_parse_fails_loudly():
    with pytest.raises(ValueError, match="none passed the check"):
        tracker.save(None, [], WEEK)


def test_save_twice_adds_nothing():
    try:
        conn = tracker.connect()
    except (KeyError, psycopg.OperationalError):
        pytest.skip("no warehouse reachable")
    try:
        conn.execute((tracker.ROOT / "sql" / "schema.sql").read_text())
        conn.execute("INSERT INTO seller (seller_id, name, base_url) VALUES ('test-seller', 'Test', 'https://shop.example')")
        rows = [GOOD,
                {**GOOD, "listing_key": URL + "-b", "url": URL + "-b", "price": Decimal("1350.25")},
                {**GOOD, "listing_key": URL + "-c", "url": URL + "-c", "price": Decimal("0")}]

        def totals():
            return conn.execute(
                "SELECT (SELECT count(*) FROM offer WHERE seller_id = 'test-seller'),"
                " count(*), sum(price), md5(string_agg(listing_key || ':' || price, ',' ORDER BY listing_key)),"
                " (SELECT count(*) FROM quarantine WHERE seller_id = 'test-seller')"
                " FROM price_observation WHERE seller_id = 'test-seller'"
            ).fetchone()

        assert tracker.save(conn, rows, WEEK) == (2, 1)
        first = totals()
        assert tracker.save(conn, rows, WEEK) == (2, 1)
        assert totals() == first
        assert first[:3] == (2, 2, Decimal("1700.50")) and first[4] == 1
        with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
            conn.execute("UPDATE price_observation SET price = 1 WHERE seller_id = 'test-seller'")
    finally:
        conn.rollback()
        conn.close()
