-- Silver: parsed, typed and checked. The competitor sites, the retailer's catalogue, what each site
-- sells (offer, enriched with part type, car and part code), every price ever seen
-- (price_observation, append-only), rejected rows (quarantine), which catalogue part each offer is
-- (offer_match) and the alert emails sent. Safe to run again: load_reference runs it every week.

CREATE SCHEMA IF NOT EXISTS silver;

CREATE TABLE IF NOT EXISTS silver.seller (    -- one row per competitor site (data/sellers.csv)
    seller_id      text PRIMARY KEY,
    name           text NOT NULL,
    base_url       text NOT NULL,
    robots_verdict text,                      -- what the site's robots.txt allows us
    crawl_delay_s  integer
);

CREATE TABLE IF NOT EXISTS silver.part (      -- one row per catalogue part of the retailer (data/catalogue.csv)
    part_no     text PRIMARY KEY,             -- text so leading zeros survive
    brand       text NOT NULL,
    family      text NOT NULL CHECK (family IN
                ('filter', 'brake pad', 'spark plug', 'battery', 'belt', 'bulb', 'wiper', 'oil')),
    name        text NOT NULL,
    car_key     text,                         -- the car it fits (make-model[-from-to]); NULL = not one car
    our_price   numeric(10, 2) NOT NULL CHECK (our_price > 0),  -- EGP
    is_key      boolean NOT NULL,             -- key parts get the undercut alert
    match_grade text NOT NULL CHECK (match_grade IN ('part_number', 'type_model')),
    match_key   text NOT NULL,                -- part code|pack, or part type|car model[|position]|pack
    UNIQUE (match_grade, match_key)
);

CREATE TABLE IF NOT EXISTS silver.offer (     -- one row per listing as one seller sells it
    seller_id   text NOT NULL REFERENCES silver.seller,
    listing_key text NOT NULL,                -- the site's product id (some sites: the page path)
    family      text NOT NULL CHECK (family IN
                ('filter', 'brake pad', 'spark plug', 'battery', 'belt', 'bulb', 'wiper', 'oil')),  -- the listing page's category
    title       text NOT NULL,
    brand       text,
    part_no     text,                         -- the site's part number as given; NULL = none
    url         text NOT NULL,
    first_seen  date NOT NULL,
    last_seen   date NOT NULL,
    -- From the title (enrich.py); NULL = the title does not say.
    part_type   text CHECK (part_type IN ('oil filter', 'air filter', 'fuel filter', 'cabin filter', 'filter',
                'brake pad', 'spark plug', 'battery', 'belt', 'bulb', 'wiper', 'oil')),
    position    text CHECK (position IN ('front', 'rear')),  -- brake pads only
    pack        text NOT NULL CHECK (pack IN ('set', 'single')),  -- 'set' when the title says several pieces
    car_make    text,
    car_model   text,
    year_from   integer,
    year_to     integer,
    car_key     text,                         -- make-model[-year_from-year_to], lower-case ASCII
    part_code   text,                         -- the code matched on: a belt size or a maker's code
    PRIMARY KEY (seller_id, listing_key)
);

CREATE TABLE IF NOT EXISTS silver.price_observation ( -- one row per offer per day seen; never updated or deleted
    seller_id     text NOT NULL,
    listing_key   text NOT NULL,
    observed_on   date NOT NULL,              -- the UTC day the page was fetched (from index.jsonl)
    price         numeric(10, 2) NOT NULL CHECK (price > 0),  -- EGP
    is_discounted boolean NOT NULL,
    in_stock      boolean,                    -- NULL = the site does not say
    run_week      date NOT NULL,              -- the weekly run that loaded it
    fetched_at    timestamptz NOT NULL,
    PRIMARY KEY (seller_id, listing_key, observed_on),
    FOREIGN KEY (seller_id, listing_key) REFERENCES silver.offer
);

-- Append-only is enforced, not hoped for: an UPDATE or DELETE on the price history fails loudly.
CREATE OR REPLACE FUNCTION silver.price_history_is_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'price_observation is append-only: % refused', TG_OP;
END $$;
CREATE OR REPLACE TRIGGER price_observation_append_only
    BEFORE UPDATE OR DELETE ON silver.price_observation
    FOR EACH ROW EXECUTE FUNCTION silver.price_history_is_append_only();

CREATE TABLE IF NOT EXISTS silver.quarantine ( -- one row per parsed row that failed the check
    id         bigserial PRIMARY KEY,
    seller_id  text NOT NULL REFERENCES silver.seller,
    run_week   date NOT NULL,
    url        text,
    reason     text NOT NULL,
    raw        jsonb NOT NULL,                -- the parsed row as it came
    fetched_at timestamptz
);
-- The same rejected row in the same run is kept once, so a rerun on cached pages adds nothing.
CREATE UNIQUE INDEX IF NOT EXISTS quarantine_once ON silver.quarantine (seller_id, run_week, md5(raw::text));

CREATE TABLE IF NOT EXISTS silver.offer_match ( -- one row per offer that is one of our parts; rebuilt by match
    seller_id   text NOT NULL,
    listing_key text NOT NULL,
    part_no     text NOT NULL REFERENCES silver.part,
    match_grade text NOT NULL CHECK (match_grade IN ('part_number', 'type_model')),
    match_key   text NOT NULL,
    comparable  boolean NOT NULL,             -- false: priced above 3x or below 1/3 of its group's median
    PRIMARY KEY (seller_id, listing_key),
    FOREIGN KEY (seller_id, listing_key) REFERENCES silver.offer
);

CREATE TABLE IF NOT EXISTS silver.alert_sent ( -- one row per run week whose alert email was sent
    run_week       date PRIMARY KEY,
    undercut_count integer NOT NULL,
    sent_at        timestamptz NOT NULL
);
