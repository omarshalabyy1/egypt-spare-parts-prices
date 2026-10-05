"""Spare-part prices, once a week: load the reference data, fetch the competitor pages, parse the
offers, match them to our parts, and email an alert where a competitor is cheaper.

Each run covers one week (its data interval); run_week is the Monday the interval ends on. Web pages
only show today's price, so the past cannot be scraped: start_date is one week back, so catchup
starts exactly one run (run_week 2026-10-05) and from then on one run a week.
"""

from datetime import datetime, timedelta, timezone

from airflow.sdk import dag, task
from airflow.timetables.interval import DeltaDataIntervalTimetable

import tracker


@dag(
    # Said explicitly: since Airflow 3 a plain timedelta schedule gives runs no data interval.
    schedule=DeltaDataIntervalTimetable(timedelta(weeks=1)),
    start_date=datetime(2026, 9, 28, tzinfo=timezone.utc),
    catchup=True,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=5)},
)
def spare_parts_prices():
    @task
    def load_reference():
        tracker.load_reference()

    @task
    def fetch_pages(seller_id, data_interval_end=None):
        tracker.fetch_pages(seller_id, tracker.week_of(data_interval_end.date()))

    @task
    def parse_offers(data_interval_end=None):
        tracker.parse_offers(tracker.week_of(data_interval_end.date()))

    @task
    def match():
        tracker.match()

    @task
    def send_alert(data_interval_end=None):
        tracker.send_alert(tracker.week_of(data_interval_end.date()))

    # One fetch task per site, run side by side; each keeps its own one-request-per-3-seconds pace.
    fetched = fetch_pages.expand(seller_id=list(tracker.SCRAPERS))
    load_reference() >> fetched >> parse_offers() >> match() >> send_alert()


spare_parts_prices()
