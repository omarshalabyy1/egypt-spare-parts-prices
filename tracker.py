"""The weekly steps Airflow runs: load the reference data, fetch the competitor pages, parse the
offers, match them to our parts, and email an alert where a competitor is cheaper. One function each."""

import csv
import gzip
import json
import os
from datetime import date, timedelta
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

import scrape
from scrapers import (amazon, autospare, egycarparts, fitandfix, garageilla, getradingeg, jumia, nautoexpress,
                      pringi, sparezone, tawfiqia, yourparts, zaitandfilters)

ROOT = Path(__file__).parent
# One scraper per competitor site, keyed by its seller_id in data/sellers.csv.
SCRAPERS = {m.__name__.split(".")[-1]: m for m in (
    amazon, autospare, egycarparts, fitandfix, garageilla, getradingeg, jumia, nautoexpress, pringi, sparezone,
    tawfiqia, yourparts, zaitandfilters)}
MAX_PAGES = 250  # per PAGES entry; a listing longer than this is cut off, with a log line


def week_of(day):
    """The Monday of the day's week: the run_week of a weekly run that ends on that day."""
    return day - timedelta(days=day.weekday())


def connect():
    return psycopg.connect(
        host=os.environ.get("WAREHOUSE_HOST", "localhost"),
        port=os.environ.get("WAREHOUSE_PORT", "5450"),
        dbname="parts",
        user="parts",
        password=os.environ["WAREHOUSE_PASSWORD"],
        connect_timeout=10,
    )


# --- Step 1: reference data ------------------------------------------------------------------

def load_reference():
    """Create the tables and views, then load the competitor sites and our catalogue from data/."""
    with connect() as conn:
        conn.execute((ROOT / "sql" / "schema.sql").read_text())
        for table, key, file in (("seller", "seller_id", "sellers.csv"), ("part", "part_no", "catalogue.csv")):
            with open(ROOT / "data" / file, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = [[r[c] or None for c in reader.fieldnames] for r in reader]
            cols = reader.fieldnames
            updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c != key)
            conn.cursor().executemany(
                f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) "
                f"ON CONFLICT ({key}) DO UPDATE SET {updates}",
                rows,
            )
            print(f"{table}: {len(rows)} rows loaded")


# --- Step 2: fetch ----------------------------------------------------------------------------

def walk(scraper, first, read):
    """The pages of one listing, from its first URL, following its next links; a list of links (a
    sitemap) fans out to each page in it. read(url) gives a page's bytes, or None if not found.
    Yields (url, body, offers, from_list); stops at the scraper's page cap."""
    queue, cap = [(first, False)], getattr(scraper, "MAX_PAGES", MAX_PAGES)
    for _ in range(cap):
        if not queue:
            return
        url, from_list = queue.pop(0)
        body = read(url)
        found, following = scraper.parse(body, url) if body is not None else ([], None)
        yield url, body, found, from_list
        if isinstance(following, list):
            queue += [(u, True) for u in following]
        elif following:
            queue.append((following, False))
    if queue:
        print(f"PAGE CAP: stopped at {cap} pages of {first}, {len(queue)} more were linked")


def fetch_pages(seller_id, run_week):
    """Fetch every listing page of one site for the week. The kept pages under data/raw are the
    output. Fails at the end if a listing page was not found; a page named in a sitemap that is
    gone (404) is only counted."""
    scraper = SCRAPERS[seller_id]
    fetch = getattr(scraper, "fetch", scrape.fetch)  # a site with its own way in (a POST) brings it
    missing, gone = [], 0
    for family, first in scraper.PAGES:
        for url, body, _, from_list in walk(scraper, first, lambda u: fetch(u, seller_id, run_week)):
            if body is None and from_list:
                gone += 1
            elif body is None:
                missing.append(url)
    print(f"{seller_id}: {gone} sitemap pages gone")
    if missing:
        raise RuntimeError(f"{seller_id}: {len(missing)} listing page(s) not found: {missing}")


# --- Step 3: parse -----------------------------------------------------------------------------

def offers(seller_id, run_week):
    """Every offer on the site's kept pages for the week, read from disk only. Walks each listing
    the way fetch_pages did, so each offer carries its listing's family (unless the parser set one);
    observed_on and fetched_at come from the page's index.jsonl line. Fails if a page is missing or
    nothing parses."""
    scraper = SCRAPERS[seller_id]
    folder = ROOT / "data" / "raw" / seller_id / str(run_week)
    good, gone = {}, set()
    with open(folder / "index.jsonl", encoding="utf-8") as f:  # no index: nothing was fetched, fail
        for line in map(json.loads, f):
            if line["status"] == 200:
                good[line["url"]] = line  # the last good fetch of a URL wins
            else:
                gone.add(line["url"])

    def read(url):
        if url in good:
            with gzip.open(ROOT / good[url]["path"]) as page:
                return page.read()
        if url in gone:
            return None
        raise RuntimeError(f"{seller_id}: {url} is not among the kept pages of {run_week}")

    rows, read_urls, skipped = [], set(), 0
    for family, first in scraper.PAGES:
        for url, body, found, from_list in walk(scraper, first, read):
            if body is None and not from_list:
                raise RuntimeError(f"{seller_id}: listing page {url} was not found when fetched")
            if body is None:
                skipped += 1
                continue
            read_urls.add(url)
            line = good[url]
            observed_on = date.fromisoformat(line["fetched_at"][:10])  # the UTC day of the fetch
            rows += [{**o, "seller_id": seller_id, "family": o.get("family") or family,
                      "observed_on": observed_on, "fetched_at": line["fetched_at"]} for o in found]
    if not rows:
        raise ValueError(f"{seller_id}: {len(read_urls)} kept pages parsed to no offers: a parser is broken")
    repeats = len(rows) - len({r["listing_key"] for r in rows})
    print(f"{seller_id}: {len(read_urls)} pages, {len(rows)} offers ({repeats} listed twice or more),"
          f" {skipped} sitemap pages gone, {len(good) - len(read_urls)} kept pages not on any listing")
    return rows


def parse_offers(run_week):
    """Parse every site's kept pages for the week and save the offers, in one transaction."""
    with connect() as conn:
        for seller_id in SCRAPERS:
            saved, quarantined = save(conn, offers(seller_id, run_week), run_week)
            print(f"{seller_id}: {saved} saved, {quarantined} quarantined")


# --- Steps 4 and 5: not written yet ----------------------------------------------------------------

def match():
    print("match: not implemented yet")


def send_alert(run_week):
    print("send_alert: not implemented yet")


# --- Saving parsed offers ----------------------------------------------------------------------

def save(conn, rows, run_week):
    """Check each parsed offer; send the bad ones to quarantine, upsert the good ones into offer
    (latest title, brand, part number, url and last_seen win) and add their prices to the history
    (never overwritten). Returns (saved, quarantined).

    Each row: seller_id, listing_key, family, title, brand, part_no, url, price (Decimal), currency,
    is_discounted, observed_on, fetched_at, and optionally in_stock and car_make (None = not stated). observed_on and fetched_at must come from the page's
    index.jsonl line, not the clock, so a rerun on the cached pages adds nothing."""
    good = []
    for row in ({"in_stock": None, "car_make": None, **r} for r in rows):
        reason = scrape.check(row)
        if reason:
            quarantine(conn, row["seller_id"], run_week, row.get("url"), reason, row)
        else:
            good.append(row)
    if not good:
        raise ValueError(f"{len(rows)} rows parsed, none passed the check: a parser is broken")
    cur = conn.cursor()
    cur.executemany(
        "INSERT INTO offer (seller_id, listing_key, family, title, brand, part_no, car_make, url, first_seen,"
        " last_seen) VALUES (%(seller_id)s, %(listing_key)s, %(family)s, %(title)s, %(brand)s, %(part_no)s,"
        " %(car_make)s, %(url)s, %(observed_on)s, %(observed_on)s)"
        " ON CONFLICT (seller_id, listing_key) DO UPDATE SET family = EXCLUDED.family, car_make = EXCLUDED.car_make,"
        " title = EXCLUDED.title, brand = EXCLUDED.brand,"
        " part_no = EXCLUDED.part_no, url = EXCLUDED.url, first_seen = least(offer.first_seen, EXCLUDED.first_seen),"
        " last_seen = greatest(offer.last_seen, EXCLUDED.last_seen)",
        good,
    )
    cur.executemany(
        "INSERT INTO price_observation (seller_id, listing_key, observed_on, price, is_discounted, in_stock,"
        " run_week, fetched_at) VALUES (%(seller_id)s, %(listing_key)s, %(observed_on)s, %(price)s,"
        " %(is_discounted)s, %(in_stock)s, %(run_week)s, %(fetched_at)s) ON CONFLICT DO NOTHING",
        [{**r, "run_week": run_week} for r in good],
    )
    return len(good), len(rows) - len(good)


def quarantine(conn, seller_id, run_week, url, reason, raw):
    """Keep a row that failed the check, as it came, with the reason. The same row twice in one
    run is kept once."""
    conn.execute(
        "INSERT INTO quarantine (seller_id, run_week, url, reason, raw, fetched_at)"
        " VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
        (seller_id, run_week, url, reason, Jsonb(raw, dumps=lambda o: json.dumps(o, default=str)),
         raw.get("fetched_at")),
    )
