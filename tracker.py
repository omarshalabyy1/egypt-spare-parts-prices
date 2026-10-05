"""The weekly steps Airflow runs: load the reference data, fetch the competitor pages, load the
parsed offers into silver, match them to our parts, rebuild the gold star, and email an alert where
a competitor is cheaper. One function each."""

import csv
import gzip
import importlib
import json
import os
import smtplib
import statistics
from collections import defaultdict
from datetime import date, timedelta
from email.message import EmailMessage

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

import enrich
import scrape
from config import ROOT, load_config

CONFIG = load_config()
# One scraper per competitor site, keyed by its seller_id, in the order of sellers in config/client.yaml
# (the longest fetch first, so it starts in the first wave of fetch tasks).
SCRAPERS = {s["seller_id"]: importlib.import_module(f"scrapers.{s['scraper']}") for s in CONFIG["sellers"]}
MAX_PAGES = 250  # per PAGES entry; a listing longer than this is cut off, with a log line
COMPARABLE_RATIO = 3  # an offer priced above 3x or below 1/3 of its match group's median is not comparable
UNDERCUT_PCT = CONFIG["rules"]["undercut_pct"]  # a competitor at least this percent below our price undercuts us


def week_of(day):
    """The Monday of the day's week: the run_week of a weekly run that ends on that day."""
    return day - timedelta(days=day.weekday())


def run_week(data_interval_end, run_after):
    """The run_week of a DAG run: the Monday of its data interval's end. A manual run triggered with
    no logical date has no data interval, so it takes the Monday of when it was triggered (run_after)."""
    return week_of((data_interval_end or run_after).date())


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

LAYERS = ("bronze.sql", "silver.sql", "gold.sql")


def load_reference():
    """Create the schemas, tables and views of each layer, then load the competitor sites from
    config/client.yaml and our catalogue from data/input/."""
    with connect() as conn:
        load_reference_into(conn)


def load_reference_into(conn):
    """load_reference on an open connection. A part no longer in the catalogue is deleted (its offer
    matches first), so a catalogue change never leaves a stale part behind. The undercut percent is
    set on the database, so every later connection (the alert, the notebook, Power BI) reads the
    same value in the gold views, and on this session too."""
    conn.execute(sql.SQL("ALTER DATABASE {} SET client.undercut_pct = {}").format(
        sql.Identifier(conn.info.dbname), sql.Literal(str(UNDERCUT_PCT))))
    conn.execute("SELECT set_config('client.undercut_pct', %s, false)", (str(UNDERCUT_PCT),))
    for file in LAYERS:
        conn.execute((ROOT / "sql" / file).read_text(encoding="utf-8"))
    seller_cols = ["seller_id", "name", "base_url", "robots_verdict", "crawl_delay_s"]
    with open(CONFIG["input_dir"] / CONFIG["inputs"]["catalogue"], newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        part_rows = [[r[c] or None for c in reader.fieldnames] for r in reader]
    for table, key, cols, rows in (
        ("silver.seller", "seller_id", seller_cols, [[s[c] for c in seller_cols] for s in CONFIG["sellers"]]),
        ("silver.part", "part_no", reader.fieldnames, part_rows),
    ):
        updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c != key)
        conn.cursor().executemany(
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) "
            f"ON CONFLICT ({key}) DO UPDATE SET {updates}",
            rows,
        )
        print(f"{table}: {len(rows)} rows loaded")
    part_nos = [row[cols.index("part_no")] for row in rows]  # the catalogue's rows, loaded last
    conn.execute("DELETE FROM silver.offer_match WHERE part_no <> ALL(%s)", (part_nos,))
    gone = conn.execute("DELETE FROM silver.part WHERE part_no <> ALL(%s)", (part_nos,)).rowcount
    print(f"silver.part: {gone} parts no longer in the catalogue deleted")


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


def load_pages(conn, seller_id, run_week):
    """The site's index.jsonl for the week into bronze.page; a line already loaded is skipped. A line
    with no via was fetched by the weekly run ('requests')."""
    with open(ROOT / "data" / "raw" / seller_id / str(run_week) / "index.jsonl", encoding="utf-8") as f:
        lines = [{"via": "requests", **json.loads(line), "seller_id": seller_id, "run_week": run_week} for line in f]
    conn.cursor().executemany(
        "INSERT INTO bronze.page (seller_id, run_week, url, path, status, fetched_at, via) VALUES (%(seller_id)s,"
        " %(run_week)s, %(url)s, %(path)s, %(status)s, %(fetched_at)s, %(via)s) ON CONFLICT DO NOTHING",
        lines,
    )
    return len(lines)


def load_silver(run_week):
    """Load every site's page index into bronze, then parse its kept pages for the week and save the
    offers into silver, in one transaction: a site that fails leaves nothing of the week behind."""
    print(f"load_silver: run_week {run_week}")
    with connect() as conn:
        for seller_id in SCRAPERS:
            pages = load_pages(conn, seller_id, run_week)
            saved, quarantined = save(conn, offers(seller_id, run_week), run_week)
            print(f"{seller_id}: {pages} pages, {saved} offers saved, {quarantined} quarantined")


# --- Step 4: match ------------------------------------------------------------------------------

def match_groups(rows):
    """Which group each offer belongs to: {(seller_id, listing_key): (match_grade, match_key)}.
    First by part code, when two sellers or more sell that code ('part_number'); then the offers
    left, by part type and car model (and position, for brake pads) sold by two sellers or more
    ('type_model'). Both are split by pack: a set and a single piece are never one part. A plain
    'filter' and a brake pad of unknown position are never grouped by type: either could be one of
    several parts. The car model carries its generation when the title names one (nissan-sunny-n17):
    such an offer compares only with the same generation, an offer naming none only with others
    naming none. A belt carries what it drives (timing or drive) the same way. Each row: seller_id,
    listing_key, part_code, part_type, position, pack, belt_function, car_make, car_model, generation."""
    def shared(keys):
        sellers = defaultdict(set)
        for (seller_id, _), key in keys.items():
            sellers[key].add(seller_id)
        return {offer: key for offer, key in keys.items() if len(sellers[key]) >= 2}

    codes = {(r["seller_id"], r["listing_key"]): f"{r['part_code']}|{r['pack']}" for r in rows if r["part_code"]}
    groups = {offer: ("part_number", key) for offer, key in shared(codes).items()}
    types = {}
    for r in rows:
        offer = (r["seller_id"], r["listing_key"])
        if offer in groups or not r["car_model"] or r["part_type"] in (None, "filter"):
            continue
        if r["part_type"] == "brake pad" and not r["position"]:
            continue
        car = f"{r['car_make']}-{r['car_model']}" + (f"-{r['generation'].lower()}" if r["generation"] else "")
        types[offer] = "|".join(x for x in (r["part_type"], r["belt_function"], car, r["position"], r["pack"]) if x)
    groups.update({offer: ("type_model", key) for offer, key in shared(types).items()})
    return groups


def median_price(offers_):
    """The median price of offers, each (seller, title, price) counted once: a seller listing the same
    thing under several cars or pages is one price, not several."""
    return statistics.median(p for _, _, p in {(o["seller_id"], o["title"], o["price"]) for o in offers_})


def group_medians(offers_, groups):
    """{group: median price} for the groups with at least 3 distinct (seller, title, price) offers,
    each offer at its latest price. A smaller group has no median to be far from."""
    members = defaultdict(list)
    for o in offers_:
        group = groups.get((o["seller_id"], o["listing_key"]))
        if group:
            members[group].append(o)
    return {group: median_price(found) for group, found in members.items()
            if len({(o["seller_id"], o["title"], o["price"]) for o in found}) >= 3}


def comparable(price, median):
    """Whether an offer's price is within COMPARABLE_RATIO of its group's median (None: the group is
    too small to tell, so every offer is comparable). A price above 3 times the median, or below a
    third of it, is another thing sold under the same words (a bundle, a single clip) and is left
    out of our price, the gaps and the undercuts."""
    return median is None or median / COMPARABLE_RATIO <= price <= median * COMPARABLE_RATIO


LATEST_OFFERS = """
SELECT DISTINCT ON (o.seller_id, o.listing_key) o.seller_id, o.listing_key, o.title, p.price, p.in_stock, o.brand,
       o.family, o.part_type, o.position, o.pack, o.belt_function, o.car_make, o.car_model, o.generation, o.car_key,
       o.part_code
FROM silver.offer o JOIN silver.price_observation p USING (seller_id, listing_key)
ORDER BY o.seller_id, o.listing_key, p.observed_on DESC
"""


def match():
    """Rebuild silver.offer_match: each offer in a match group maps to that group's catalogue part,
    flagged comparable = false when its latest price is far off the group's median."""
    with connect() as conn:
        offers_ = conn.cursor(row_factory=dict_row).execute(LATEST_OFFERS).fetchall()
        groups = match_groups(offers_)
        medians = group_medians(offers_, groups)
        parts = {(grade, key): part_no for part_no, grade, key in
                 conn.execute("SELECT part_no, match_grade, match_key FROM silver.part")}
        rows = []
        for o in offers_:
            group = groups.get((o["seller_id"], o["listing_key"]))
            if group in parts:
                rows.append((o["seller_id"], o["listing_key"], parts[group], *group,
                             comparable(o["price"], medians.get(group))))
        if not rows:
            raise ValueError(f"{len(groups)} offers in match groups, none maps to a catalogue part:"
                             " is the catalogue in data/input/ loaded?")
        conn.execute("DELETE FROM silver.offer_match")
        conn.cursor().executemany("INSERT INTO silver.offer_match (seller_id, listing_key, part_no, match_grade,"
                                  " match_key, comparable) VALUES (%s, %s, %s, %s, %s, %s)", rows)
        print(f"match: {len(offers_)} offers, {len(groups)} in match groups, {len(rows)} matched to"
              f" {len({r[2] for r in rows})} catalogue parts, {sum(not r[5] for r in rows)} not comparable")


# --- Step 5: gold -------------------------------------------------------------------------------

BUILD_GOLD = """
TRUNCATE gold.fact_price_observation, gold.dim_part, gold.dim_seller, gold.dim_date;

INSERT INTO gold.dim_seller (seller_key, seller_id, name, base_url)
SELECT row_number() OVER (ORDER BY seller_id), seller_id, name, base_url FROM silver.seller;

INSERT INTO gold.dim_part (part_key, part_no, name, family, brand, car_key, our_price, is_key)
SELECT 0, 'unmatched', 'Not one of our parts', 'n/a', 'n/a', NULL, NULL, false
UNION ALL
SELECT row_number() OVER (ORDER BY part_no), part_no, name, family, brand, car_key, our_price, is_key
FROM silver.part;

INSERT INTO gold.dim_date (date_key, date, run_week, iso_year, iso_week, month)
SELECT to_char(d, 'YYYYMMDD')::int, d, date_trunc('week', d)::date, extract(isoyear FROM d)::int,
       extract(week FROM d)::int, date_trunc('month', d)::date
FROM generate_series((SELECT least(min(observed_on), min(run_week)) FROM silver.price_observation),
                     (SELECT greatest(max(observed_on), max(run_week)) FROM silver.price_observation),
                     interval '1 day') AS d;

-- One row per offer per run week (silver's run_week, the run folder): the week's last observation.
INSERT INTO gold.fact_price_observation (date_key, observed_on, seller_key, part_key, listing_key, match_grade,
                                         comparable, price, in_stock, is_discounted, part_type, car_key)
SELECT DISTINCT ON (o.seller_id, o.listing_key, o.run_week)
       to_char(o.run_week, 'YYYYMMDD')::int, o.observed_on, s.seller_key, coalesce(p.part_key, 0), o.listing_key,
       m.match_grade, m.comparable, o.price, o.in_stock, o.is_discounted, x.part_type, x.car_key
FROM silver.price_observation o
JOIN silver.offer x USING (seller_id, listing_key)
JOIN gold.dim_seller s USING (seller_id)
LEFT JOIN silver.offer_match m USING (seller_id, listing_key)
LEFT JOIN gold.dim_part p ON p.part_no = m.part_no
ORDER BY o.seller_id, o.listing_key, o.run_week, o.observed_on DESC;
"""


def build_gold():
    """Rebuild the gold star from silver in one transaction (truncate, then insert). Fails if the
    fact comes out empty."""
    with connect() as conn:
        conn.execute(BUILD_GOLD)
        counts = conn.execute(
            "SELECT (SELECT count(*) FROM gold.dim_seller), (SELECT count(*) FROM gold.dim_part),"
            " (SELECT count(*) FROM gold.dim_date), (SELECT count(*) FROM gold.fact_price_observation),"
            " (SELECT count(*) FROM gold.fact_price_observation WHERE part_key <> 0)").fetchone()
        if not counts[3]:
            raise ValueError("gold.fact_price_observation came out empty: is silver loaded?")
        print("build_gold: dim_seller {}, dim_part {}, dim_date {}, fact {} ({} matched)".format(*counts))


# --- Step 6: alert ------------------------------------------------------------------------------

def send_alert(run_week):
    """Email this run week's rows of gold.undercut_alert: a seller cut a key part's price, or listed it
    new, to at least UNDERCUT_PCT below ours. A week with no earlier week is a baseline and alerts
    nothing. Without GMAIL_USER and GMAIL_APP_PASSWORD the count is logged and no email is sent."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT part_no, name, seller_id, reason, old_price, their_price, our_price, gap_pct FROM gold.undercut_alert"
            " WHERE run_week = %s ORDER BY gap_pct DESC, part_no, seller_id", (run_week,)).fetchall()
        earlier = conn.execute("SELECT count(*) FROM gold.fact_price_observation JOIN gold.dim_date USING (date_key)"
                               " WHERE run_week < %s", (run_week,)).fetchone()[0]
        if not earlier:
            print(f"Run week {run_week} is the baseline week: no previous prices, {len(rows)} alerts")
            return
        if not rows:
            print(f"0 alerts in run week {run_week}: no key-part price cut to {UNDERCUT_PCT}% or more below ours")
            return
        if not (os.environ.get("GMAIL_USER") and os.environ.get("GMAIL_APP_PASSWORD")):
            print(f"{len(rows)} alerts in run week {run_week}, but GMAIL_USER and GMAIL_APP_PASSWORD are not set in"
                  " .env: no email")
            return
        message = EmailMessage()
        message["Subject"] = f"Spare parts price alert: {len(rows)} key-part undercuts (week of {run_week})"
        message["From"] = os.environ["GMAIL_USER"]
        message["To"] = os.environ.get("MAIL_TO") or os.environ["GMAIL_USER"]
        message.set_content("\n".join(
            [f"Competitors cut these key parts to {UNDERCUT_PCT}% or more below our price"
             f" (week of {run_week}, prices in EGP):", ""]
            + [f"- {part_no} {name}: {seller_id} {f'{old} -> ' if old else 'new at '}{theirs}"
               f" (ours {ours}, we are {gap}% dearer)"
               for part_no, name, seller_id, reason, old, theirs, ours, gap in rows]))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(os.environ["GMAIL_USER"], os.environ["GMAIL_APP_PASSWORD"])
            smtp.send_message(message)
        conn.execute(
            "INSERT INTO silver.alert_sent (run_week, undercut_count, sent_at) VALUES (%s, %s, now())"
            " ON CONFLICT (run_week) DO UPDATE SET undercut_count = EXCLUDED.undercut_count, sent_at = now()",
            (run_week, len(rows)))
        print(f"Alert sent: {len(rows)} key-part undercuts")


# --- Saving parsed offers ----------------------------------------------------------------------

def save(conn, rows, run_week):
    """Keep the first row of each listing (a listing on two pages of a site is one offer); check
    each, send the bad ones to quarantine, enrich the good ones from their title (enrich.py), upsert
    them into silver.offer (latest title, brand, part number, url, enrichment and last_seen win) and
    add their prices to the history (never overwritten). Returns (saved, quarantined).

    Each row: seller_id, listing_key, family, title, brand, part_no, url, price (Decimal), currency,
    is_discounted, observed_on, fetched_at, and optionally in_stock and car_make (the car the site
    states; None = not stated). observed_on and fetched_at must come from the page's index.jsonl
    line, not the clock, so a rerun on the cached pages adds nothing."""
    first, keyless = {}, []  # a row with no listing_key is never merged: each one goes to quarantine
    for row in rows:
        if row.get("listing_key"):
            first.setdefault(row["listing_key"], row)
        else:
            keyless.append(row)
    kept = [*first.values(), *keyless]
    good = []
    for row in ({"in_stock": None, "car_make": None, **r} for r in kept):
        reason = scrape.check(row)
        if reason:
            quarantine(conn, row["seller_id"], run_week, row.get("url"), reason, row)
            continue
        part_type, position, pack = enrich.part_type(row["title"])
        car_make, car_model, year_from, year_to, car_key = enrich.car(row["title"], row["car_make"])
        good.append({**row, "part_type": part_type, "position": position, "pack": pack, "car_make": car_make,
                     "car_model": car_model,
                     "generation": enrich.generation(row["title"], row["car_make"], car_model, year_from, year_to),
                     "belt_function": enrich.belt_function(row["title"]) if part_type == "belt" else None,
                     "year_from": year_from, "year_to": year_to, "car_key": car_key,
                     "part_code": enrich.part_code(row["part_no"], row["title"])})
    if not good:
        raise ValueError(f"{len(rows)} rows parsed, none passed the check: a parser is broken")
    cur = conn.cursor()
    cur.executemany(
        "INSERT INTO silver.offer (seller_id, listing_key, family, title, brand, part_no, url, first_seen, last_seen,"
        " part_type, position, pack, belt_function, car_make, car_model, generation, year_from, year_to, car_key,"
        " part_code) VALUES (%(seller_id)s, %(listing_key)s, %(family)s, %(title)s, %(brand)s, %(part_no)s, %(url)s,"
        " %(observed_on)s, %(observed_on)s, %(part_type)s, %(position)s, %(pack)s, %(belt_function)s, %(car_make)s,"
        " %(car_model)s, %(generation)s,"
        " %(year_from)s,"
        " %(year_to)s,"
        " %(car_key)s, %(part_code)s)"
        " ON CONFLICT (seller_id, listing_key) DO UPDATE SET family = EXCLUDED.family, title = EXCLUDED.title,"
        " brand = EXCLUDED.brand, part_no = EXCLUDED.part_no, url = EXCLUDED.url,"
        " first_seen = least(offer.first_seen, EXCLUDED.first_seen),"
        " last_seen = greatest(offer.last_seen, EXCLUDED.last_seen), part_type = EXCLUDED.part_type,"
        " position = EXCLUDED.position, pack = EXCLUDED.pack, belt_function = EXCLUDED.belt_function,"
        " car_make = EXCLUDED.car_make,"
        " car_model = EXCLUDED.car_model, generation = EXCLUDED.generation,"
        " year_from = EXCLUDED.year_from, year_to = EXCLUDED.year_to, car_key = EXCLUDED.car_key,"
        " part_code = EXCLUDED.part_code",
        good,
    )
    cur.executemany(
        "INSERT INTO silver.price_observation (seller_id, listing_key, observed_on, price, is_discounted, in_stock,"
        " run_week, fetched_at) VALUES (%(seller_id)s, %(listing_key)s, %(observed_on)s, %(price)s,"
        " %(is_discounted)s, %(in_stock)s, %(run_week)s, %(fetched_at)s) ON CONFLICT DO NOTHING",
        [{**r, "run_week": run_week} for r in good],
    )
    return len(good), len(kept) - len(good)


def quarantine(conn, seller_id, run_week, url, reason, raw):
    """Keep a row that failed the check, as it came, with the reason. The same row twice in one
    run is kept once."""
    conn.execute(
        "INSERT INTO silver.quarantine (seller_id, run_week, url, reason, raw, fetched_at)"
        " VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
        (seller_id, run_week, url, reason, Jsonb(raw, dumps=lambda o: json.dumps(o, default=str)),
         raw.get("fetched_at")),
    )
