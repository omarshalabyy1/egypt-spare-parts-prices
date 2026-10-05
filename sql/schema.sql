-- The warehouse: the competitor sites, the retailer's catalogue, what each site sells (offer), every
-- price ever seen (price_observation, append-only), rejected rows (quarantine) and the views the alert
-- reads. Safe to run again: load_reference runs it at the start of every weekly run. A view whose
-- columns change must be dropped first (CREATE OR REPLACE VIEW only adds columns at the end).

CREATE TABLE IF NOT EXISTS seller (           -- one row per competitor site (data/sellers.csv)
    seller_id      text PRIMARY KEY,
    name           text NOT NULL,
    base_url       text NOT NULL,
    robots_verdict text,                      -- what the site's robots.txt allows us
    crawl_delay_s  integer
);

CREATE TABLE IF NOT EXISTS part (             -- one row per catalogue part of the retailer (data/catalogue.csv)
    part_no   text PRIMARY KEY,               -- text so leading zeros survive
    brand     text NOT NULL,
    family    text NOT NULL CHECK (family IN
              ('filter', 'brake pad', 'spark plug', 'battery', 'belt', 'bulb', 'wiper', 'oil')),
    name      text NOT NULL,
    fits      text,                           -- the car model
    our_price numeric(10, 2) NOT NULL CHECK (our_price > 0),  -- EGP
    is_key    boolean NOT NULL                -- key parts get the undercut alert
);

CREATE TABLE IF NOT EXISTS offer (            -- one row per listing as one seller sells it
    seller_id       text NOT NULL REFERENCES seller,
    listing_key     text NOT NULL,            -- the site's product id (sparezone: the page path)
    title           text NOT NULL,
    brand           text,
    part_no         text,                     -- the site's SKU where it is a maker code; NULL = none
    url             text NOT NULL,
    part_no_matched text REFERENCES part,     -- set by the match step; NULL = not a part we sell
    match_method    text CHECK (match_method IN ('part_no', 'name')),
    match_score     numeric(4, 3),
    first_seen      date NOT NULL,
    last_seen       date NOT NULL,
    PRIMARY KEY (seller_id, listing_key)
);
-- The family of the listing page the offer was found on. For a mixed category it is a first guess
-- the match step refines. Added after the first create, so a warehouse made earlier gets it too.
ALTER TABLE offer ADD COLUMN IF NOT EXISTS family text NOT NULL CHECK (family IN
    ('filter', 'brake pad', 'spark plug', 'battery', 'belt', 'bulb', 'wiper', 'oil'));
-- The car the listing is for, as the site states it (a make, or a model with years); NULL = not stated.
ALTER TABLE offer ADD COLUMN IF NOT EXISTS car_make text;

CREATE TABLE IF NOT EXISTS price_observation ( -- one row per offer per day seen; never updated or deleted
    seller_id     text NOT NULL,
    listing_key   text NOT NULL,
    observed_on   date NOT NULL,              -- the day the page was fetched (from index.jsonl)
    price         numeric(10, 2) NOT NULL CHECK (price > 0),  -- EGP
    is_discounted boolean NOT NULL,
    run_week      date NOT NULL,              -- the weekly run that loaded it (its data interval start)
    fetched_at    timestamptz NOT NULL,
    PRIMARY KEY (seller_id, listing_key, observed_on),
    FOREIGN KEY (seller_id, listing_key) REFERENCES offer
);

-- Whether the site showed the offer in stock that day; NULL = the site does not say.
ALTER TABLE price_observation ADD COLUMN IF NOT EXISTS in_stock boolean;

-- Append-only is enforced, not hoped for: an UPDATE or DELETE on the price history fails loudly.
CREATE OR REPLACE FUNCTION price_history_is_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'price_observation is append-only: % refused', TG_OP;
END $$;
CREATE OR REPLACE TRIGGER price_observation_append_only
    BEFORE UPDATE OR DELETE ON price_observation
    FOR EACH ROW EXECUTE FUNCTION price_history_is_append_only();

CREATE TABLE IF NOT EXISTS quarantine (       -- one row per parsed row that failed the schema check
    id         bigserial PRIMARY KEY,
    seller_id  text NOT NULL REFERENCES seller,
    run_week   date NOT NULL,
    url        text,
    reason     text NOT NULL,
    raw        jsonb NOT NULL,                -- the parsed row as it came
    fetched_at timestamptz
);
-- The same rejected row in the same run is kept once, so a rerun on cached pages adds nothing.
CREATE UNIQUE INDEX IF NOT EXISTS quarantine_once ON quarantine (seller_id, run_week, md5(raw::text));

CREATE TABLE IF NOT EXISTS alert_sent (       -- one row per alert email
    run_week       date PRIMARY KEY,
    undercut_count integer NOT NULL,
    sent_at        timestamptz NOT NULL
);

-- The latest price of every offer.
CREATE OR REPLACE VIEW latest_price AS
SELECT DISTINCT ON (seller_id, listing_key)
       seller_id, listing_key, observed_on, price, is_discounted, run_week, fetched_at
FROM price_observation
ORDER BY seller_id, listing_key, observed_on DESC;

-- One row per matched part per seller: our price against the seller's latest price. Only offers seen
-- in the seller's latest weekly run count: a listing gone from the site no longer undercuts us. When a
-- seller has the part in several listings, the cheapest wins: it is the price a customer could pay.
-- gap_egp > 0 means we are dearer.
CREATE OR REPLACE VIEW price_gap AS
SELECT DISTINCT ON (o.part_no_matched, o.seller_id)
       o.part_no_matched AS part_no, o.seller_id, o.listing_key, o.url, l.observed_on,
       p.our_price, l.price AS their_price, p.our_price - l.price AS gap_egp,
       round((p.our_price - l.price) / p.our_price * 100, 1) AS gap_pct, p.is_key
FROM latest_price l
JOIN offer o USING (seller_id, listing_key)
JOIN part p ON p.part_no = o.part_no_matched
WHERE l.run_week = (SELECT max(run_week) FROM price_observation WHERE seller_id = l.seller_id)
ORDER BY o.part_no_matched, o.seller_id, l.price, o.listing_key;

-- Where a seller is cheaper than us.
CREATE OR REPLACE VIEW undercut AS
SELECT * FROM price_gap WHERE their_price < our_price;

-- Every price change of an offer: a day's price that differs from the offer's previous price.
CREATE OR REPLACE VIEW price_change AS
SELECT t.seller_id, t.listing_key, o.part_no_matched AS part_no, t.observed_on, t.old_price,
       t.price AS new_price, t.price - t.old_price AS change_egp,
       round((t.price - t.old_price) / t.old_price * 100, 1) AS change_pct, t.run_week
FROM (
    SELECT p.*, lag(p.price) OVER (PARTITION BY p.seller_id, p.listing_key ORDER BY p.observed_on) AS old_price
    FROM price_observation p
) t
JOIN offer o USING (seller_id, listing_key)
WHERE t.old_price IS NOT NULL AND t.price <> t.old_price;
