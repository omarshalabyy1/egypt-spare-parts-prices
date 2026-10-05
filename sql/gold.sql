-- Gold: a Kimball star for Power BI, rebuilt in full from silver by build_gold every run, and the
-- views the alert and the report read. Safe to run again: load_reference runs it every week. A view
-- whose columns change must be dropped first (CREATE OR REPLACE VIEW only adds columns at the end).

CREATE SCHEMA IF NOT EXISTS gold;

CREATE TABLE IF NOT EXISTS gold.dim_seller (  -- one row per competitor site
    seller_key integer PRIMARY KEY,
    seller_id  text NOT NULL UNIQUE,
    name       text NOT NULL,
    base_url   text NOT NULL
);

CREATE TABLE IF NOT EXISTS gold.dim_part (    -- one row per catalogue part, plus part_key 0 = unmatched
    part_key  integer PRIMARY KEY,
    part_no   text NOT NULL UNIQUE,
    name      text NOT NULL,
    family    text NOT NULL,
    brand     text NOT NULL,
    car_key   text,
    our_price numeric(10, 2),                 -- EGP; NULL on the unmatched member
    is_key    boolean NOT NULL
);

CREATE TABLE IF NOT EXISTS gold.dim_date (    -- one row per day from the first to the last day observed
    date_key integer PRIMARY KEY,             -- yyyymmdd
    date     date NOT NULL UNIQUE,
    run_week date NOT NULL,                   -- the Monday of the date's week
    iso_year integer NOT NULL,
    iso_week integer NOT NULL,
    month    date NOT NULL                    -- the first day of the month
);

CREATE TABLE IF NOT EXISTS gold.fact_price_observation ( -- grain: one offer per run week
    date_key      integer NOT NULL REFERENCES gold.dim_date,    -- the run week (its Monday), from silver's run_week
    observed_on   date NOT NULL,                                -- the day of the week's last observation
    seller_key    integer NOT NULL REFERENCES gold.dim_seller,
    part_key      integer NOT NULL REFERENCES gold.dim_part,    -- 0 = not one of our parts
    listing_key   text NOT NULL,                                -- degenerate dimension: the seller's product id
    match_grade   text CHECK (match_grade IN ('part_number', 'type_model')),  -- NULL when unmatched
    comparable    boolean,                                      -- false: priced far off its group (silver.offer_match); NULL when unmatched
    price         numeric(10, 2) NOT NULL,                      -- EGP
    in_stock      boolean,
    is_discounted boolean NOT NULL,
    part_type     text,
    car_key       text,
    PRIMARY KEY (seller_key, listing_key, date_key)
);

-- One row per matched part per seller: our price against the seller's price in the seller's latest
-- run week. When a seller has the part in several listings, the cheapest one not shown out of stock
-- wins: it is the price a customer could pay. An offer priced far off its group (comparable = false)
-- is left out. gap_egp > 0 means we are dearer.
CREATE OR REPLACE VIEW gold.price_gap AS
SELECT DISTINCT ON (p.part_no, s.seller_id)
       p.part_no, p.name, p.family, p.is_key, s.seller_id, f.listing_key, d.run_week, f.observed_on,
       p.our_price, f.price AS their_price, p.our_price - f.price AS gap_egp,
       round((p.our_price - f.price) / p.our_price * 100, 1) AS gap_pct, f.match_grade, f.in_stock
FROM gold.fact_price_observation f
JOIN gold.dim_part p USING (part_key)
JOIN gold.dim_seller s USING (seller_key)
JOIN gold.dim_date d USING (date_key)
WHERE f.part_key <> 0 AND f.comparable
  AND d.run_week = (SELECT max(d2.run_week) FROM gold.fact_price_observation f2
                    JOIN gold.dim_date d2 USING (date_key) WHERE f2.seller_key = f.seller_key)
ORDER BY p.part_no, s.seller_id, f.in_stock IS FALSE, f.price, f.listing_key;

-- Where a seller is at least client.undercut_pct (5) percent cheaper than us and does not show the
-- part out of stock. The percent is rules.undercut_pct in config/client.yaml, set on the database by
-- load_reference.
CREATE OR REPLACE VIEW gold.undercut AS
SELECT * FROM gold.price_gap
WHERE their_price <= our_price * (1 - current_setting('client.undercut_pct')::numeric / 100) AND in_stock IS NOT FALSE;

-- What the alert emails: one row per key part's comparable offer, not shown out of stock, that this
-- run week is at least client.undercut_pct percent below our price and either cut its price from
-- its previous observed week ('price cut') or is new this week at a seller already tracked in an
-- earlier week ('new offer'). A seller's first tracked week is its baseline: no alert.
CREATE OR REPLACE VIEW gold.undercut_alert AS
SELECT run_week, part_no, name, seller_id, listing_key, observed_on,
       CASE WHEN old_price IS NULL THEN 'new offer' ELSE 'price cut' END AS reason,
       old_price, their_price, our_price, our_price - their_price AS gap_egp,
       round((our_price - their_price) / our_price * 100, 1) AS gap_pct, match_grade
FROM (
    SELECT d.run_week, f.observed_on, p.part_no, p.name, p.is_key, p.our_price, s.seller_id, f.listing_key,
           f.price AS their_price, f.comparable, f.in_stock, f.match_grade,
           lag(f.price) OVER (PARTITION BY f.seller_key, f.listing_key ORDER BY d.run_week) AS old_price,
           min(d.run_week) OVER (PARTITION BY f.seller_key) AS seller_first_week
    FROM gold.fact_price_observation f
    JOIN gold.dim_part p USING (part_key)
    JOIN gold.dim_seller s USING (seller_key)
    JOIN gold.dim_date d USING (date_key)
) t
WHERE is_key AND comparable AND in_stock IS NOT FALSE
  AND their_price <= our_price * (1 - current_setting('client.undercut_pct')::numeric / 100)
  AND (their_price < old_price OR (old_price IS NULL AND run_week > seller_first_week));

-- Every price change of an offer from one run week to the next. Empty until a second week is loaded.
CREATE OR REPLACE VIEW gold.price_change AS
SELECT seller_id, listing_key, part_no, run_week, old_price, new_price, new_price - old_price AS change_egp,
       round((new_price - old_price) / old_price * 100, 1) AS change_pct, match_grade
FROM (
    SELECT s.seller_id, f.listing_key, p.part_no, d.run_week, f.price AS new_price, f.match_grade,
           lag(f.price) OVER (PARTITION BY f.seller_key, f.listing_key ORDER BY d.run_week) AS old_price
    FROM gold.fact_price_observation f
    JOIN gold.dim_seller s USING (seller_key)
    JOIN gold.dim_part p USING (part_key)
    JOIN gold.dim_date d USING (date_key)
) t
WHERE old_price IS NOT NULL AND new_price <> old_price;
