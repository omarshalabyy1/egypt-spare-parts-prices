-- Bronze: the pages as fetched. The pages themselves stay on disk, gzipped under
-- data/raw/<seller_id>/<run_week>/ with one index.jsonl line per request; this table is that index,
-- loaded by load_silver. Safe to run again: load_reference runs it at the start of every weekly run.

CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.page (      -- one row per fetched page (one index.jsonl line)
    seller_id  text NOT NULL,
    run_week   date NOT NULL,                 -- the weekly run that fetched it (the folder name)
    url        text NOT NULL,
    path       text,                          -- the kept file under data/raw; NULL when not kept (a 4xx)
    status     integer NOT NULL,              -- the HTTP status
    fetched_at timestamptz NOT NULL,
    via        text,                          -- 'browser' for scripts/fetch_with_browser.py; NULL = the weekly run
    PRIMARY KEY (seller_id, run_week, url, fetched_at)
);
