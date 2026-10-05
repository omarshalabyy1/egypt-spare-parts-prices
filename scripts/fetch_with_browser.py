"""Fetch one seller's listing pages through a visible Chromium window that Omar operates, for a site
that blocks the automated run. When a challenge, login or cookie banner shows, Omar clears it himself
in the window and presses Enter; this script never clicks, solves or types anything on the page.

The browser profile (cookies, login) is kept in .browser-profile/<seller_id>/ so later weeks reuse it.
Pages land in the same cache as scrape.fetch: data/raw/<seller_id>/<run_week>/, one index.jsonl line
each, plus "via": "browser".

Usage: python scripts/fetch_with_browser.py <seller_id> [--week YYYY-MM-DD] [--headless] [--max-pages N]
"""

import argparse
import gzip
import hashlib
import importlib
import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from playwright.sync_api import TimeoutError as PlaywrightTimeout, sync_playwright  # noqa: E402

import scrape  # noqa: E402

DELAY_S = 5  # one page every 5 seconds
BLOCKED = (401, 403, 429)
PROMPT = "Clear the challenge, log in or accept cookies in the browser window, then press Enter to retry this page"


def load(page, url, reload=False):
    """(status, body) of the page once the network is idle; a JSON route keeps its raw body."""
    response = page.reload() if reload else page.goto(url, wait_until="domcontentloaded")
    try:
        page.wait_for_load_state("networkidle", timeout=15_000)
    except PlaywrightTimeout:
        pass  # a page that keeps polling never goes idle; take what has loaded
    status = response.status if response else 0
    if response and "json" in response.headers.get("content-type", ""):
        return status, response.body()
    return status, page.content().encode()


def keep(url, seller_id, run_week, status, body):
    """Write the page and its index.jsonl line the way scrape.fetch does; a 4xx/5xx keeps no file."""
    folder = ROOT / "data" / "raw" / seller_id / run_week
    folder.mkdir(parents=True, exist_ok=True)
    ok = status < 400
    name = hashlib.sha1(url.encode()).hexdigest()[:12]
    path = folder / f"{name}.{'json' if body.lstrip()[:1] in (b'[', b'{') else 'html'}.gz"
    if ok:
        path.write_bytes(gzip.compress(body, mtime=0))
    with open(folder / "index.jsonl", "a", encoding="utf-8") as index:
        index.write(json.dumps({
            "url": url,
            "path": path.relative_to(ROOT).as_posix() if ok else None,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "via": "browser",
        }) + "\n")


def main():
    args = argparse.ArgumentParser()
    args.add_argument("seller_id")
    args.add_argument("--week", help="run_week (a Monday); default: the Monday of this UTC week")
    args.add_argument("--headless", action="store_true")
    args.add_argument("--max-pages", type=int, default=None, help="pages per family (default 250)")
    a = args.parse_args()
    today = datetime.now(timezone.utc).date()
    run_week = a.week or str(today - timedelta(days=today.weekday()))
    date.fromisoformat(run_week)  # fails on a malformed --week
    scraper = importlib.import_module(f"scrapers.{a.seller_id}")
    cap = a.max_pages or getattr(scraper, "MAX_PAGES", 250)
    summary = []

    with sync_playwright() as p:
        probe = p.chromium.launch(headless=a.headless)
        user_agent = probe.new_page().evaluate("navigator.userAgent") + " " + scrape.USER_AGENT
        probe.close()
        context = p.chromium.launch_persistent_context(
            str(ROOT / ".browser-profile" / a.seller_id), headless=a.headless, user_agent=user_agent)
        page = context.pages[0] if context.pages else context.new_page()
        try:
            for family, first in scraper.PAGES:
                queue, pages, offers = [first], 0, 0
                while queue and pages < cap:
                    url, first_page = queue.pop(0), pages == 0
                    pages += 1
                    cached = scrape.kept(url, a.seller_id, run_week)
                    if cached:  # already kept this week: parse from disk, no request
                        with gzip.open(cached) as f:
                            found, following = scraper.parse(f.read(), url)
                    else:
                        for attempt in (1, 2):
                            started = time.monotonic()
                            status, body = load(page, url, reload=attempt == 2)
                            found, following = scraper.parse(body, url) if status < 400 else ([], None)
                            time.sleep(max(0, DELAY_S - (time.monotonic() - started)))
                            empty = first_page and not found and not following
                            if status not in BLOCKED and not empty:
                                break
                            if attempt == 1:
                                print(f"{url}: status {status}, {len(found)} offers. {PROMPT}")
                                input()
                        keep(url, a.seller_id, run_week, status, body)
                        if status in BLOCKED or empty:
                            print(f"{url}: still blocked or empty after a retry (status {status}); next family")
                            break
                    offers += len(found)
                    queue += following if isinstance(following, list) else [following] if following else []
                if queue and pages >= cap:
                    print(f"PAGE CAP: stopped at {cap} pages of {first}, {len(queue)} more were linked")
                summary.append((family, first, pages, offers))
        finally:
            context.close()  # flushes the profile so the cookies persist
    for family, first, pages, offers in summary:
        print(f"{a.seller_id} {family} {first}: {pages} pages, {offers} offers")


if __name__ == "__main__":
    main()
