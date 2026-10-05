"""Checks against the warehouse: a part dropped from the catalogue is deleted, and the alert view
alerts on a price cut or a new offer, never in a seller's baseline week. Each test runs only when
the warehouse is reachable (WAREHOUSE_PASSWORD set) and rolls back."""

import csv

import psycopg
import pytest

import tracker


@pytest.fixture
def conn():
    try:
        connection = tracker.connect()
    except (KeyError, psycopg.OperationalError):
        pytest.skip("no warehouse reachable")
    yield connection
    connection.rollback()
    connection.close()


def test_part_no_longer_in_the_catalogue_is_deleted(conn):
    tracker.load_reference_into(conn)
    conn.execute("INSERT INTO silver.offer (seller_id, listing_key, family, title, url, first_seen, last_seen, pack)"
                 " VALUES ('amazon', 'test-stale', 'belt', 'Test belt', 'https://x.example', '2026-10-05', '2026-10-05',"
                 " 'single')")
    conn.execute("INSERT INTO silver.part (part_no, brand, family, name, our_price, is_key, match_grade, match_key)"
                 " VALUES ('EG-STALE00', 'Generic', 'belt', 'Belt TEST', 100, false, 'part_number', 'TEST|single')")
    conn.execute("INSERT INTO silver.offer_match VALUES ('amazon', 'test-stale', 'EG-STALE00', 'part_number',"
                 " 'TEST|single', true)")
    tracker.load_reference_into(conn)
    with open(tracker.CONFIG["input_dir"] / tracker.CONFIG["inputs"]["catalogue"], newline="", encoding="utf-8") as f:
        in_csv = {r["part_no"] for r in csv.DictReader(f)}
    assert {p for p, in conn.execute("SELECT part_no FROM silver.part")} == in_csv
    assert conn.execute("SELECT count(*) FROM silver.offer_match WHERE part_no = 'EG-STALE00'").fetchone()[0] == 0


def test_undercut_alert_needs_a_price_cut_or_a_new_offer_after_the_baseline(conn):
    tracker.load_reference_into(conn)
    conn.execute("INSERT INTO gold.dim_seller VALUES (9001, 'test-old', 'Test', 'https://x.example'),"
                 " (9002, 'test-new', 'Test', 'https://y.example')")
    conn.execute("INSERT INTO gold.dim_part VALUES (9001, 'EG-TEST0001', 'Belt TEST', 'belt', 'Generic', NULL, 100, true)")
    conn.execute("INSERT INTO gold.dim_date VALUES (20300107, '2030-01-07', '2030-01-07', 2030, 2, '2030-01-01'),"
                 " (20300114, '2030-01-14', '2030-01-14', 2030, 3, '2030-01-01')")
    facts = [  # seller, listing, day, price
        (9001, "cut", 20300107, 90), (9001, "cut", 20300114, 80),  # baseline at 90, then cut to 80: alert
        (9001, "same", 20300107, 90), (9001, "same", 20300114, 90),  # 10% below us both weeks, no cut: none
        (9001, "new", 20300114, 90),  # new this week at a seller tracked before: alert
        (9001, "near", 20300114, 96),  # new, but only 4% below us: none
        (9002, "first", 20300114, 50),  # the seller's first week is its baseline: none
    ]
    conn.cursor().executemany(
        "INSERT INTO gold.fact_price_observation (date_key, observed_on, seller_key, part_key, listing_key, match_grade,"
        " comparable, price, in_stock, is_discounted) VALUES (%s, to_date(%s::text, 'YYYYMMDD'), %s, 9001, %s,"
        " 'part_number', true, %s, NULL, false)",
        [(day, day, seller, listing, price) for seller, listing, day, price in facts])
    alerts = conn.execute("SELECT run_week::text, seller_id, listing_key, reason, old_price FROM gold.undercut_alert"
                          " WHERE seller_id LIKE 'test-%' ORDER BY listing_key").fetchall()
    assert alerts == [("2030-01-14", "test-old", "cut", "price cut", 90), ("2030-01-14", "test-old", "new", "new offer", None)]
