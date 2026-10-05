# 2. The model

Open **Model view** (the third icon on the left).

## Tables

Row counts are from the run of 5 October 2026 (see `06-checks.md`, check C2).

| Table | Grain (one row per) | Surrogate key | Natural key | Rows |
|---|---|---|---|---|
| `Seller` | competitor site | `seller_key` | `seller_id` | 13 |
| `Part` | catalogue part, plus `part_key` 0 = none of ours | `part_key` | `part_no` | 870 |
| `Date` | day observed, first to last, no gaps | `date_key` (yyyymmdd) | `date` | `count(*)` of `gold.dim_date` (1 today) |
| `Match Grade` | way an offer is matched to our part | none | `match_grade` | 2 |
| `Offer` | seller's listing in the latest run week | none | `seller_key` + `listing_key` + `date_key` | 28,825 |
| `Price Gap` | our part per seller: the seller's cheapest comparable listing not shown out of stock, in its latest run week | none | `part_no` + `seller_id` | 2,343 |
| `_Measures` | holds the measures only | none | none | 1 (hidden) |

A small star: two facts that each keep their own grain, sharing the `Seller`, `Part` and
`Match Grade` dimensions. `Offer` answers "what did the run read"; `Price Gap` answers "where do we
stand against each seller". The `_Measures` table is created in step 3 (`03-measures.dax`). There are
no calculated columns and no calculated tables: every column comes from Power Query.

Why two facts and not one: an offer and a price gap have different grains. A part sold by a seller
in three listings is three offers but one price gap (the cheapest listing), so the two are never
added together.

`Part` keeps `part_key` 0 (`part_no` `unmatched`) so every offer has a part; the measures that count
our parts leave it out. `Date` has one row per day the run observed; with one run week loaded that is
one day.

## Mark the date table

Select the `Date` table, then **Table tools > Mark as date table**, and pick the `date` column.

Why: `date` has one row per day with no gaps, so weeks and months group correctly; `date_key` stays
the column the relationship uses. Turn off **File > Options and settings > Options > Current file >
Data load > Auto date/time** so Power BI does not add hidden date tables of its own.

## Relationships

Drag each "one" column onto its "many" column, then open the relationship (double-click the line)
and check the settings.

| From (one) | To (many) | Cardinality | Cross-filter direction | Active | Why |
|---|---|---|---|---|---|
| `Seller[seller_key]` | `Offer[seller_key]` | One to many | Single | Yes | A seller filters its offers |
| `Part[part_key]` | `Offer[part_key]` | One to many | Single | Yes | A part filters its offers (and its market's middle price) |
| `Date[date_key]` | `Offer[date_key]` | One to many | Single | Yes | An offer is dated by its run week |
| `Match Grade[match_grade]` | `Offer[match_grade]` | One to many | Single | Yes | The Match slicer filters the matched offers |
| `Seller[seller_id]` | `Price Gap[seller_id]` | One to many | Single | Yes | A seller filters its prices against ours; `gold.price_gap` carries the natural key |
| `Part[part_no]` | `Price Gap[part_no]` | One to many | Single | Yes | A part (and its family) filters the gaps; natural key, as above |
| `Match Grade[match_grade]` | `Price Gap[match_grade]` | One to many | Single | Yes | The Match slicer filters the gaps |

Power BI may create some of these on its own when you close Power Query. Delete any other
relationship it made (for example between `Offer` and `Price Gap` on `listing_key`, or `Part` and
`Offer` on `car_key`): a path between the two facts makes the model ambiguous.

Why single direction everywhere: filters flow from the small tables to the facts, never back, so
every number has one meaning.

Why `Price Gap` has no Date relationship: it holds each seller's latest price only, so it answers
"where do we stand now"; filtering it by a past date would mean nothing.

Why `Seller` and `Part` reach `Price Gap` by their natural keys: the view carries `seller_id` and
`part_no`, both unique in their dimension, so no lookup step is needed in Power Query.

Why a `Match Grade` table and not a slicer on `Offer[match_grade]`: one slicer must filter both facts,
and the offers that are none of ours have no grade. The offer counts ignore the slicer on purpose
(their measures remove its filter, `03-measures.dax`).

## Hide columns

Hide the columns a report builder should not pick, so slicers and axes always use a dimension
(right-click > Hide in report view):

- `Offer`: every column except `Car model` (`date_key`, `seller_key`, `part_key`, `listing_key`,
  `match_grade`, `comparable`, `price`, `in_stock`, `car_key`, `Usable`). Keys belong to the
  dimensions; the prices and flags are read by measures only.
- `Price Gap`: every column (`part_no`, `seller_id`, `listing_key`, `our_price`, `their_price`,
  `gap_pct`, `match_grade`, `Undercut`): the measures read them; the pages use `Part` and `Seller`.
- `Part[part_key]`, `Part[car_key]`, `Part[is_key]`, `Part[Measured]`: keys and flags the measures
  use; no page shows them.
- `Seller[seller_key]`, `Seller[seller_id]`: keys; the pages show `Seller[name]`.
- `Match Grade[match_grade]`: the slicer shows `Grade`.
- `Date[date_key]`: a key.
- The empty column of `_Measures` (after step 3).

## Sort by column

Select `Match Grade[Grade]`, then **Column tools > Sort by column > match_grade**, so "Exact part
number" (`part_number`) always comes first in the slicer, whatever the labels say.

## Column formats

Set in **Column tools > Format** with the column selected.

| Column | Format | Why |
|---|---|---|
| `Part[our_price]`, `Offer[price]`, `Price Gap[our_price]`, `Price Gap[their_price]` | Fixed decimal, 2 decimals, thousands separator on, no currency symbol | Egyptian pounds to the piastre; the page titles say EGP |
| `Price Gap[gap_pct]` | Decimal number, 1 decimal | Already in percent with one decimal: 26.4 means our price is 26.4% above the seller's |
| `Date[date]`, `Date[run_week]`, `Date[month]` | Short date (`yyyy-mm-dd`) | Same as the warehouse and the checks |
| `Date[iso_year]`, `Date[iso_week]` | Whole number, thousands separator off | A year and a week number, not counts |

## Display folders

Set on each measure in step 3 (**Properties pane > Display folder**):

| Folder | Measures |
|---|---|
| Overview | Sellers, Offers, Parts Matched, Parts Undercut, Share Undercut |
| Labels | Page Label |
| Gaps | Parts Measured, Cheapest Price, Dearest Price, Our Price, Cheapest Seller, Gap To Cheapest, Spread, Median Gap, Median Spread |
| Sellers | Market Middle Price, Cheapest In, Cheapest Share, Price Index |
