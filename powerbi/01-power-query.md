# 1. Power Query

The report reads the gold star of the local warehouse: PostgreSQL at `127.0.0.1:5450`, database
`parts`, after `docker compose up -d` and a weekly run of the `spare_parts_prices` DAG (steps 1 to 4
of [`08-build-checklist.md`](08-build-checklist.md)). Nothing is read from files, and nothing from
bronze or silver.

Open Power BI Desktop, then **Home > Transform data** to open the Power Query editor. For each query
below: **Home > New source > Blank query**, rename it (right-click > Rename) to the name in the
heading, open **Home > Advanced editor**, delete what is there and paste the code. Create them in
the order of this file: a query can only refer to one created before it.

| Query | Source | Rows (run of 5 October 2026) | Columns | Load |
|---|---|---|---|---|
| `WarehouseServer` | parameter (text) | none | none | no (parameter) |
| `WarehouseDatabase` | parameter (text) | none | none | no (parameter) |
| `Seller` | `gold.dim_seller` | 13 | 3 | yes |
| `Offer` | `gold.fact_price_observation`, the latest run week | 28,825 | 11 (9 + `Usable` + `Car model`) | yes |
| `Part Market` | `Offer`, the usable offers counted per part | one per part with a usable offer | 3 | no (staging) |
| `Part` | `gold.dim_part`, with `Measured` from `Part Market` | 936 | 8 (7 + `Measured`) | yes |
| `Match Grade` | the match grades found in `Offer` | 2 | 2 (1 + `Grade`) | yes |
| `Undercut` | `gold.undercut` | 1,415 | 2 | no (staging) |
| `Price Gap` | `gold.price_gap`, not shown out of stock, with `Undercut` | 2,429 | 8 (7 + `Undercut`) | yes |
| `Date` | `gold.dim_date` | one per day observed | 6 | yes |

The gold columns read, as `information_schema.columns` lists them:

| Table or view | Columns (type) |
|---|---|
| `gold.dim_seller` | `seller_key` integer, `seller_id` text, `name` text, `base_url` text |
| `gold.dim_part` | `part_key` integer, `part_no` text, `name` text, `family` text, `brand` text, `car_key` text, `our_price` numeric, `is_key` boolean |
| `gold.dim_date` | `date_key` integer, `date` date, `run_week` date, `iso_year` integer, `iso_week` integer, `month` date |
| `gold.fact_price_observation` | `date_key` integer, `observed_on` date, `seller_key` integer, `part_key` integer, `listing_key` text, `match_grade` text, `comparable` boolean, `price` numeric, `in_stock` boolean, `is_discounted` boolean, `part_type` text, `car_key` text |
| `gold.price_gap` | `part_no` text, `name` text, `family` text, `is_key` boolean, `seller_id` text, `listing_key` text, `run_week` date, `observed_on` date, `our_price` numeric, `their_price` numeric, `gap_egp` numeric, `gap_pct` numeric, `match_grade` text, `in_stock` boolean |
| `gold.undercut` | as `gold.price_gap` |

Why no renames: the column names match [`sql/gold.sql`](../sql/gold.sql) and the SQL in
`06-checks.md`, so a number on a card can be checked against the warehouse word for word. Visuals
show friendly names, set on the visual (`04-pages.md`). The three added columns have readable names
because they exist only here.

Why the gold views and not a rule of our own: `gold.price_gap` already keeps each seller's cheapest
comparable listing of a part in its latest run week, and `gold.undercut` already says which of them
is at least 5% below our price (`rules.undercut_pct` in `config/client.yaml`). The alert email, the notebook and
this report then read the same rule, written once in SQL.

Why every column gets a type: Power BI then never guesses, so a refresh after a new run cannot turn
a price into text.

Why "not shown out of stock" is a Power Query column and never a DAX filter: `in_stock` is empty
(null) where the site does not say. In Power Query, `null <> false` is true, so an offer whose stock
is unknown is kept, as the notebook and the views keep it. In DAX, a blank equals FALSE, so a filter
`in_stock <> FALSE()` would drop those offers (485 comparable matched offers in the run of 5 October
2026).

## The first connection

The first query you create asks for credentials: choose **Database**, user `parts`, password =
`WAREHOUSE_PASSWORD` from the repo's `.env`, and apply them to `127.0.0.1:5450`. If Power BI says it
cannot connect with encryption, choose **OK** to connect without it: the warehouse listens on your
laptop only. Use `127.0.0.1`, not `localhost`.

## WarehouseServer and WarehouseDatabase (parameters)

**Home > Manage parameters > New parameter**, twice:

- Name: `WarehouseServer`, Type: Text, Current value: `127.0.0.1:5450`
- Name: `WarehouseDatabase`, Type: Text, Current value: `parts`

Why parameters: the queries name no server or database, so another warehouse changes two values, not
six queries.

## Seller (loads)

The competitor sites: one row per seller.

```m
let
    Source = PostgreSQL.Database(WarehouseServer, WarehouseDatabase),
    dim_seller = Source{[Schema = "gold", Item = "dim_seller"]}[Data],
    Kept = Table.SelectColumns(dim_seller, {"seller_key", "seller_id", "name"}),
    Typed = Table.TransformColumnTypes(Kept, {
        {"seller_key", Int64.Type}, {"seller_id", type text}, {"name", type text}})
in
    Typed
```

Applied steps: `Source` (the warehouse), `dim_seller` (the table), `Kept` (drops `base_url`, not
used), `Typed`.

## Offer (loads)

Every offer of the latest run week: one row per seller's listing.

```m
let
    Source = PostgreSQL.Database(WarehouseServer, WarehouseDatabase),
    fact = Source{[Schema = "gold", Item = "fact_price_observation"]}[Data],
    LatestWeek = List.Max(fact[date_key]),
    ThisWeek = if LatestWeek = null then error "gold is empty: run the DAG first"
        else Table.SelectRows(fact, each [date_key] = LatestWeek),
    Kept = Table.SelectColumns(ThisWeek, {
        "date_key", "seller_key", "part_key", "listing_key", "match_grade", "comparable", "price",
        "in_stock", "car_key"}),
    Typed = Table.TransformColumnTypes(Kept, {
        {"date_key", Int64.Type}, {"seller_key", Int64.Type}, {"part_key", Int64.Type},
        {"listing_key", type text}, {"match_grade", type text}, {"comparable", type logical},
        {"price", Currency.Type}, {"in_stock", type logical}, {"car_key", type text}}),
    Usable = Table.AddColumn(Typed, "Usable", each
        [part_key] <> 0 and [comparable] = true and [in_stock] <> false, type logical),
    CarModel = Table.AddColumn(Usable, "Car model", each
        if [car_key] = null then null
        else Text.Proper(Text.Combine(List.FirstN(Text.Split([car_key], "-"), 2), " ")), type text)
in
    CarModel
```

Applied steps:

- `LatestWeek`, `ThisWeek`: the latest run week only (`date_key` is the run week's Monday). Each
  offer is then counted once, at its price in the latest week, as in the notebook. When more weeks
  are loaded, the report still shows the latest one. When the fact is empty (`build_gold` has not
  run, or is rebuilding gold at that moment), `LatestWeek` is null and the query stops with the
  error "gold is empty: run the DAG first", so **Close & apply** and **Refresh** fail loudly instead
  of loading empty tables.
- `Kept`: drops `observed_on`, `is_discounted` and `part_type`, which no page uses.
- `Usable`: matched to one of our parts, comparable (priced within 3 times of its group's median,
  either way) and not shown out of stock. The offers a part's market and middle price are counted
  from.
- `Car model`: the car the title names, without its years: `hyundai-grand i10-2013-2020` becomes
  `Hyundai Grand I10`. A `car_key` is `make-model[-from-to]` and a model never holds a hyphen, so the
  first two parts are the make and model (the notebook strips `-yyyy-yyyy` the same way). Empty when
  the title names no car.

## Part Market (staging: do not load)

Per part, its usable offers and the sellers they come from. Right-click the query and untick
**Enable load**.

```m
let
    Usable = Table.SelectRows(Offer, each [Usable]),
    Grouped = Table.Group(Usable, {"part_key"}, {
        {"offers", each Table.RowCount(_), Int64.Type},
        {"sellers", each List.Count(List.Distinct([seller_key])), Int64.Type}})
in
    Grouped
```

## Part (loads)

Our catalogue: one row per part, plus `part_key` 0 for the offers that are none of ours.

```m
let
    Source = PostgreSQL.Database(WarehouseServer, WarehouseDatabase),
    dim_part = Source{[Schema = "gold", Item = "dim_part"]}[Data],
    Kept = Table.SelectColumns(dim_part, {"part_key", "part_no", "name", "family", "car_key", "our_price", "is_key"}),
    Typed = Table.TransformColumnTypes(Kept, {
        {"part_key", Int64.Type}, {"part_no", type text}, {"name", type text}, {"family", type text},
        {"car_key", type text}, {"our_price", Currency.Type}, {"is_key", type logical}}),
    WithMarket = Table.NestedJoin(Typed, {"part_key"}, #"Part Market", {"part_key"}, "Market", JoinKind.LeftOuter),
    Counts = Table.ExpandTableColumn(WithMarket, "Market", {"offers", "sellers"}),
    Measured = Table.AddColumn(Counts, "Measured", each
        [offers] <> null and [offers] >= 3 and [sellers] >= 2, type logical),
    Dropped = Table.RemoveColumns(Measured, {"offers", "sellers"})
in
    Dropped
```

Applied steps:

- `Kept`: drops `brand`, which no page uses.
- `WithMarket`, `Counts`: each part's usable offers and sellers from `Part Market`.
- `Measured`: the part has a market to measure: at least 3 usable offers from at least 2 sellers, the
  notebook's rule. Every gap, spread and seller number counts measured parts only.
- `Dropped`: the two counts, used only for `Measured`.

## Match Grade (loads)

The two ways an offer is matched to our part: one row per grade, for the **Match** slicer.

```m
let
    Grades = List.Sort(List.RemoveNulls(List.Distinct(Offer[match_grade]))),
    AsTable = Table.FromList(Grades, Splitter.SplitByNothing(), {"match_grade"}),
    Typed = Table.TransformColumnTypes(AsTable, {{"match_grade", type text}}),
    Grade = Table.AddColumn(Typed, "Grade", each
        if [match_grade] = "part_number" then "Exact part number"
        else if [match_grade] = "type_model" then "Same part type, same car"
        else [match_grade], type text)
in
    Grade
```

`Grade` is the readable label the slicer shows. The grades come from the offers, so a new grade in
gold shows up in the slicer under its own code.

## Undercut (staging: do not load)

The comparable offers not shown out of stock that are at least 5% below our price: one row per part
per seller. Untick **Enable load**.

```m
let
    Source = PostgreSQL.Database(WarehouseServer, WarehouseDatabase),
    undercut = Source{[Schema = "gold", Item = "undercut"]}[Data],
    Kept = Table.SelectColumns(undercut, {"part_no", "seller_id"}),
    Typed = Table.TransformColumnTypes(Kept, {{"part_no", type text}, {"seller_id", type text}})
in
    Typed
```

## Price Gap (loads)

Each seller's comparable price for each of our parts in its latest run week, against ours: one row
per part per seller, the seller's cheapest comparable listing not shown out of stock.

```m
let
    Source = PostgreSQL.Database(WarehouseServer, WarehouseDatabase),
    price_gap = Source{[Schema = "gold", Item = "price_gap"]}[Data],
    Kept = Table.SelectColumns(price_gap, {
        "part_no", "seller_id", "listing_key", "our_price", "their_price", "gap_pct", "match_grade", "in_stock"}),
    Typed = Table.TransformColumnTypes(Kept, {
        {"part_no", type text}, {"seller_id", type text}, {"listing_key", type text},
        {"our_price", Currency.Type}, {"their_price", Currency.Type}, {"gap_pct", type number},
        {"match_grade", type text}, {"in_stock", type logical}}),
    NotOutOfStock = Table.SelectRows(Typed, each [in_stock] <> false),
    WithUndercut = Table.NestedJoin(NotOutOfStock, {"part_no", "seller_id"}, Undercut, {"part_no", "seller_id"}, "Below", JoinKind.LeftOuter),
    Flagged = Table.AddColumn(WithUndercut, "Undercut", each not Table.IsEmpty([Below]), type logical),
    Dropped = Table.RemoveColumns(Flagged, {"Below", "in_stock"})
in
    Dropped
```

Applied steps:

- `Kept`: drops `name`, `family` and `is_key` (they are in `Part`), `run_week`, `observed_on` and
  `gap_egp` (not used).
- `NotOutOfStock`: drops the sellers that show the part out of stock (279 of 2,708 rows in the run
  of 5 October 2026). Both the notebook's market and `gold.undercut` leave them out.
- `WithUndercut`, `Flagged`: `Undercut` is true where the seller is in `gold.undercut` for the part.
- `gap_pct` is our price over the seller's, in percent with one decimal: 26.4 means our price is
  26.4% above the seller's. Above 0, the seller is cheaper than us.

`gold.price_gap` takes about 19 seconds to compute and `gold.undercut`, built on it, about 23
(measured on the warehouse of 5 October 2026), so **Close & apply** and each **Refresh** take close
to a minute. That is the views working, not a hang.

## Date (loads)

One row per day from the first to the last day a price was observed, from gold.

```m
let
    Source = PostgreSQL.Database(WarehouseServer, WarehouseDatabase),
    dim_date = Source{[Schema = "gold", Item = "dim_date"]}[Data],
    Typed = Table.TransformColumnTypes(dim_date, {
        {"date_key", Int64.Type}, {"date", type date}, {"run_week", type date},
        {"iso_year", Int64.Type}, {"iso_week", Int64.Type}, {"month", type date}})
in
    Typed
```

Why gold's date table and not one built here: `gold.dim_date` already has one row per day with no
gaps, and the fact's `date_key` points to it, so the report uses the same calendar as the warehouse.

**Home > Close & apply.** Then go to [`02-model.md`](02-model.md).
