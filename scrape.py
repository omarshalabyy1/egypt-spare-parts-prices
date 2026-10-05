"""The shared fetcher every site's scraper uses, and the schema check for a parsed offer.

Every page fetched is kept gzipped under data/raw/<seller_id>/<run_week>/, with one index.jsonl line
per request. A page already kept for that week is read from disk, never fetched again, so a fresh
clone re-parses the committed pages and gets the same numbers."""

import gzip
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit
from urllib.robotparser import RobotFileParser

import requests

ROOT = Path(__file__).parent
USER_AGENT = "egypt-spare-parts-prices (+https://github.com/omarshalabyy1/egypt-spare-parts-prices)"
MIN_DELAY_S = 3  # never faster than one request every 3 seconds, whatever robots.txt says
BACKOFF_S = (2, 4, 8)  # waits before each of the 3 retries on a 429, a 5xx or a dropped connection

http = requests.Session()
http.headers["User-Agent"] = USER_AGENT
_robots = {}  # host -> RobotFileParser


def robots(url):
    """The site's robots.txt, read once per host with our own User-Agent."""
    parts = urlsplit(url)
    if parts.netloc not in _robots:
        response = http.get(f"{parts.scheme}://{parts.netloc}/robots.txt", timeout=30)
        rules = RobotFileParser()
        rules.parse(response.text.splitlines() if response.ok else [])
        # A locked robots.txt means keep out; so does a server error (RFC 9309: assume complete disallow).
        rules.disallow_all = response.status_code in (401, 403) or response.status_code >= 500
        _robots[parts.netloc] = rules
        time.sleep(MIN_DELAY_S)  # the robots.txt request counts against the site's rate too
    return _robots[parts.netloc]


def allowed(url):
    return robots(url).can_fetch(USER_AGENT, url)


def kept(url, seller_id, run_week):
    """The path of the page as kept for that week, or None if it was not kept."""
    folder = ROOT / "data" / "raw" / seller_id / str(run_week)
    name = hashlib.sha1(url.encode()).hexdigest()[:12]
    return next((p for p in (folder / f"{name}.html.gz", folder / f"{name}.json.gz") if p.exists()), None)


def fetch(url, seller_id, run_week, form=None, headers=None):
    """The page as bytes (HTML or JSON, as the site sent it), or None on a 4xx. With form, the page
    is POSTed (a site's own "load more"); the URL still names it in the cache. Sleeps only after a
    live request, never after a page read from disk: requests to a site start at least 3 s apart."""
    path = kept(url, seller_id, run_week)
    if path:
        with gzip.open(path) as f:
            return f.read()
    if not allowed(url):
        raise RuntimeError(f"robots.txt does not allow {url}")
    delay = max(robots(url).crawl_delay(USER_AGENT) or 0, MIN_DELAY_S)
    folder = ROOT / "data" / "raw" / seller_id / str(run_week)
    name = hashlib.sha1(url.encode()).hexdigest()[:12]
    for backoff in (*BACKOFF_S, None):
        started = time.monotonic()
        try:
            if form is None:
                response = http.get(url, timeout=60)
            else:
                response = http.post(url.split("?")[0], data=form, headers=headers, timeout=60)
        except (requests.ConnectionError, requests.Timeout):
            response = None
        time.sleep(max(0, delay - (time.monotonic() - started)))
        if response is not None and response.status_code != 429 and response.status_code < 500:
            break
        if backoff is None:
            raise RuntimeError(f"{url}: no answer after {len(BACKOFF_S) + 1} tries "
                               f"(last status {response.status_code if response is not None else 'no connection'})")
        time.sleep(backoff)
    folder.mkdir(parents=True, exist_ok=True)
    ok = response.status_code < 400
    path = folder / f"{name}.{'json' if response.content.lstrip()[:1] in (b'[', b'{') else 'html'}.gz"
    if ok:
        path.write_bytes(gzip.compress(response.content, mtime=0))
    with open(folder / "index.jsonl", "a", encoding="utf-8") as index:
        index.write(json.dumps({
            "url": url,
            "path": path.relative_to(ROOT).as_posix() if ok else None,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "status": response.status_code,
        }) + "\n")
    return response.content if ok else None


def money(text):
    """'EGP 1,500.00', '990 EGP' or '1,850' as a Decimal; None unless the text holds exactly one number."""
    numbers = re.findall(r"\d[\d,]*(?:\.\d+)?", text or "")
    return Decimal(numbers[0].replace(",", "")) if len(numbers) == 1 else None


def next_page(url):
    """The same URL with its page=N query parameter raised by one (for the JSON listing routes)."""
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query["page"] = str(int(query.get("page", "1")) + 1)
    return parts._replace(query=urlencode(query)).geturl()


def maker_code(sku):
    """A SKU that looks like a maker's part code: letters and digits, 4 to 12 long, and not a shop's
    own digits+EG+digits code (102003012EG007)."""
    return bool(sku and re.fullmatch(r"(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9]{4,12}", sku)
                and not re.fullmatch(r"\d+EG\d+", sku))


def part_code(text):
    """A seller's part number cleaned to the code alone, or None if it is not one: '29934 (FEBI)' ->
    '29934', '0 242 129 522--BOSCH' -> '0 242 129 522', '04E109119C  S' -> '04E109119C'; a text with a
    word in it ('HX320W50 SHELL', 'DIN 105 AGM SILVER') is a description, not a code."""
    text = re.sub(r"\([^)]*\)|--.*$", " ", (text or "").split(",")[0])
    words = text.split()
    if len(words) > 1 and re.fullmatch(r"[A-Za-z]", words[-1]):
        words = words[:-1]  # a trailing one-letter marker
    code = " ".join(words)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 .\-/]{2,24}", code) or not re.search(r"\d", code):
        return None
    return None if any(re.fullmatch(r"[A-Za-z]{3,}", w) for w in words) else code


def check(row):
    """The schema check for a parsed offer: None if it is good, else the reason it is not."""
    if not isinstance(row.get("title"), str) or not row["title"].strip():
        return "title missing"
    if not str(row.get("url", "")).startswith(("http://", "https://")):
        return "url not http(s)"
    if not row.get("listing_key"):
        return "listing_key missing"
    price = row.get("price")
    if price is None:
        return "no price shown"
    if not isinstance(price, Decimal) or not 0 < price < 1_000_000:
        return "price not a Decimal between 0 and 1,000,000"
    if row.get("currency") != "EGP":
        return "currency not EGP"
    return None
