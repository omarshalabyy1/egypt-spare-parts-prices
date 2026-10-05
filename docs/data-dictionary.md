# Data dictionary: the gold layer

The gold schema is a Kimball star rebuilt in full from silver by `build_gold` every run (truncate and
insert in one transaction), plus three views on it. Prices are Egyptian pounds (EGP) to the piastre.
DDL: [sql/gold.sql](../sql/gold.sql).

## gold.dim_seller

Grain: one row per competitor site. Key: `seller_key` (surrogate); natural key `seller_id`.

| Column | Type | Meaning |
|---|---|---|
| seller_key | integer | Surrogate key, 1 to n in `seller_id` order |
| seller_id | text | The site's id in data/sellers.csv (`autospare`) |
| name | text | The site's name |
| base_url | text | The site's home page |

## gold.dim_part

Grain: one row per catalogue part of the retailer, plus one unmatched member. Key: `part_key`
(surrogate; 0 = not one of our parts); natural key `part_no`.

| Column | Type | Meaning |
|---|---|---|
| part_key | integer | Surrogate key, 1 to n in `part_no` order; 0 is the unmatched member |
| part_no | text | The retailer's part number (`EG-` and 8 hex characters; `unmatched` for 0) |
| name | text | The part's English name (`Belt 6PK1460`, `Brake pad front for Hyundai Elantra`, `Spark plug set for Kia Rio`) |
| family | text | One of filter, brake pad, spark plug, battery, belt, bulb, wiper, oil; `n/a` for 0 |
| brand | text | The brand most offers of the part name, else `Generic`; `n/a` for 0 |
| car_key | text | The car the part fits, `make-model[-from-to]`; NULL when not one car |
| our_price | numeric(10,2) | The retailer's price, EGP: the median of the part's comparable offers not shown out of stock, to 0.50 EGP (the retailer is made up); NULL for 0 |
| is_key | boolean | A key part, the undercut alert covers it: the top 20% of parts by number of sellers (ties by offers) |

## gold.dim_date

Grain: one row per day from the first to the last day a price was observed. Key: `date_key`.

| Column | Type | Meaning |
|---|---|---|
| date_key | integer | The date as yyyymmdd (20261005) |
| date | date | The day |
| run_week | date | The Monday of the day's week: the weekly run it belongs to |
| iso_year | integer | ISO 8601 year |
| iso_week | integer | ISO 8601 week number |
| month | date | The first day of the month |

## gold.fact_price_observation

Grain: one offer (one seller's listing) per run week; when an offer was seen on two days of one
week, the later day's price is the one kept. Key: (`seller_key`, `listing_key`, `date_key`).

| Column | Type | Meaning |
|---|---|---|
| date_key | integer | The day of the week's kept observation (dim_date) |
| seller_key | integer | The seller (dim_seller) |
| part_key | integer | Our part this offer is (dim_part); 0 when it is none of ours |
| listing_key | text | Degenerate dimension: the seller's own product id |
| match_grade | text | How the offer was matched: `part_number` (same part code at 2+ sellers) or `type_model` (same part type and car model at 2+ sellers), both split into sets and single pieces (a brake pad is never a set: an axle set is the unit); NULL when unmatched |
| comparable | boolean | False when the offer's price is above 3 times or below a third of its match group's median: kept here, left out of the views; NULL when unmatched |
| price | numeric(10,2) | The seller's price, EGP |
| in_stock | boolean | Whether the seller showed it in stock; NULL when the site does not say |
| is_discounted | boolean | Whether the seller showed a struck-out previous price |
| part_type | text | The part type the title names (`oil filter`, `brake pad`, ...); NULL when it names none |
| car_key | text | The car the title names, `make-model[-from-to]`; NULL when it names none |

## gold.price_gap (view)

Grain: one row per matched part per seller, in the seller's latest run week. Where a seller has the
part in several listings, the cheapest one not shown out of stock is kept. Offers not comparable
are left out.

| Column | Meaning |
|---|---|
| part_no, name, family, is_key | The part (dim_part) |
| seller_id | The seller |
| listing_key | The listing kept |
| run_week, observed_on | The run week and the day of the price |
| our_price | Our price, EGP |
| their_price | The seller's price, EGP |
| gap_egp | `our_price - their_price`: above 0, we are dearer |
| gap_pct | `gap_egp / our_price`, percent, one decimal |
| match_grade | `part_number` or `type_model` |
| in_stock | As in the fact |

## gold.undercut (view)

Grain and columns as `gold.price_gap`, only the rows where the seller is at least 5% cheaper
(`their_price <= our_price * 0.95`; `UNDERCUT_PCT` in tracker.py) and does not show the part out
of stock. `send_alert` emails the key parts in this view for
the run week.

## gold.undercut_alert (view)

Grain: one row per key part's offer per run week that the alert email lists. The offer is
comparable, not shown out of stock, at least 5% below our price (`UNDERCUT_PCT`), and either cut
its price from its previous observed week (`price cut`) or is new this week at a seller already
tracked in an earlier week (`new offer`). A seller's first tracked week is its baseline: no alerts.
`send_alert` reads this view for the run week.

| Column | Meaning |
|---|---|
| run_week, observed_on | The run week and the day of the price |
| part_no, name | The key part |
| seller_id, listing_key | The offer |
| reason | `price cut` or `new offer` |
| old_price | The offer's price in its previous observed week, EGP; NULL for a new offer |
| their_price, our_price | The seller's price and ours, EGP |
| gap_egp, gap_pct | `our_price - their_price`, and that as a percent of our price |
| match_grade | `part_number` or `type_model` |

## gold.price_change (view)

Grain: one row per offer per run week whose price differs from the offer's price in its previous
run week. Empty until a second run week is loaded.

| Column | Meaning |
|---|---|
| seller_id, listing_key | The offer |
| part_no | Our part (`unmatched` when none) |
| run_week | The week of the new price |
| old_price, new_price | The previous run week's price and this one's, EGP |
| change_egp | `new_price - old_price` |
| change_pct | `change_egp / old_price`, percent, one decimal |
| match_grade | As in the fact |
