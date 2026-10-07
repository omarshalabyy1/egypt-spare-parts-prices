# 6. Checks: the numbers the report must show

Every number below is in `analysis/numbers.json` as written by `analysis/analysis.ipynb` (commit
7c676d1, the run week of 5 October 2026) under the key named after it, and comes back from the SQL
under its check. A number marked **SQL only** has no key in `numbers.json` (the notebook does not
split it that way); the SQL is its source. If a card is off, the usual causes are a missing
relationship, a wrong column type in Power Query, a staging query left loading, or the Match slicer
on the wrong choice.

**Building after a later run?** The numbers move with each run. Run the notebook once (it rewrites
`numbers.json`), then read each check's value from its key, or from its SQL, not from this page.

Run the SQL in any SQL tool on port 5450, database `parts`, user `parts`, or with
`docker compose exec warehouse psql -U parts -d parts`. Run the market block once per session before
C9 to C14: it builds the same market the report builds (a temporary table, gone when you
disconnect). It takes about 20 seconds, the time `gold.price_gap` takes to compute.

```sql
-- The market: each seller's comparable price for each measured part, not shown out of stock, with
-- the part's middle price. A part is measured from 3 usable offers at 2 sellers or more.
CREATE TEMP TABLE market AS
WITH usable AS (
    SELECT f.part_key, f.seller_key, f.price
    FROM gold.fact_price_observation f JOIN gold.dim_date d USING (date_key)
    WHERE d.run_week = (SELECT max(run_week) FROM gold.dim_date)
      AND f.part_key <> 0 AND f.comparable AND f.in_stock IS NOT FALSE),
measured AS (
    SELECT p.part_no, percentile_cont(0.5) WITHIN GROUP (ORDER BY u.price) AS median_price
    FROM usable u JOIN gold.dim_part p USING (part_key)
    GROUP BY p.part_no HAVING count(*) >= 3 AND count(DISTINCT u.seller_key) >= 2)
SELECT g.*, m.median_price FROM gold.price_gap g JOIN measured m USING (part_no) WHERE g.in_stock IS NOT FALSE;
```

## The warehouse, before Power BI

**C1.** The run is loaded: run week 2026-10-05 (`run_week`), 28,825 offers (`offers`).

```sql
SELECT (SELECT max(run_week) FROM gold.dim_date) AS run_week,
       (SELECT count(*) FROM gold.fact_price_observation
        WHERE date_key = (SELECT max(date_key) FROM gold.fact_price_observation)) AS offers;
```

If `offers` is 0, `build_gold` has not run or is running: wait for the DAG to finish, never build on
an empty gold.

**C2.** Rows per table after **Close & apply** (Table view, bottom left): Seller 13 · Part 936 ·
Date = `date` below (1 for one run day) · Match Grade 2 · Offer 28,825 (`offers`) · Price Gap 2,429.
Part is our 935 parts (`parts`) plus the unmatched member. **SQL only:** Seller, Part, Date, Match
Grade and Price Gap.

```sql
SELECT (SELECT count(*) FROM gold.dim_seller) AS seller, (SELECT count(*) FROM gold.dim_part) AS part,
       (SELECT count(*) FROM gold.dim_date) AS date,
       (SELECT count(DISTINCT match_grade) FROM gold.fact_price_observation) AS match_grade,
       (SELECT count(*) FROM gold.fact_price_observation
        WHERE date_key = (SELECT max(date_key) FROM gold.fact_price_observation)) AS offer,
       (SELECT count(*) FROM gold.price_gap WHERE in_stock IS NOT FALSE) AS price_gap;
```

**C3.** Two cards on a blank page, no slicer yet: Offers 28,825 (`offers`) · Parts Measured 737
(`groups_measured`). 737 is the measured parts of both grades: Power Query's `Measured` flag and the
`Price Gap` table agree with the notebook.

## Page 1: Overview

**C4.** Match on **Exact part number**. The label reads "Run week 2026-10-05 · Match: Exact part
number". Cards: Sellers 13 (`sellers`) · Offers 28,825 (`offers`) · Our parts matched 154
(`parts_part_number`) · Parts with a seller 5%+ below our price 88 (`parts_below_part_number`) ·
Share of the parts matched 57.1% (`parts_below_part_number_pct`, 57.142857).

**C5.** Seller bar (#9), top to bottom (`offers_<seller_id>`): AutoSpare 9,981 · Egy Car Parts
3,832 · Tawfiqia 3,628 · Zait and Filters 3,488 · Amazon Egypt 1,718 · Jumia Egypt 1,566 · GE
Trading 1,530 · Pringi 1,308 · N Auto Express 1,135 · YourParts 283 · Fit and Fix 167 · Spare Zone
124 · Garageilla 65. They add up to 28,825. The Match slicer does not change them.

```sql
SELECT s.name, count(*) AS offers
FROM gold.fact_price_observation f JOIN gold.dim_seller s USING (seller_key)
WHERE f.date_key = (SELECT max(date_key) FROM gold.fact_price_observation)
GROUP BY s.name ORDER BY offers DESC;
```

**C6.** Car model bar (#10): 16 bars (the 15th and 16th tie). Hyundai Elantra 776 (`top_model`,
`top_model_offers`) · Kia Cerato 631 · Skoda Octavia 577 · Mitsubishi Lancer 563 · Nissan Sunny 557 ·
Toyota Corolla 514 · Hyundai Accent 456 · Renault Megane 412 · Chevrolet Optra 405 · Volkswagen Golf
391 · Renault Logan 378 · Chevrolet Aveo 361 · Hyundai Verna 354 · Volkswagen Passat 330 · Chevrolet
Cruze 325 · Opel Astra 325. **SQL only** below Hyundai Elantra. The 90 models in all are
`car_models`.

```sql
SELECT initcap(replace(regexp_replace(car_key, '-\d{4}-\d{4}$', ''), '-', ' ')) AS car_model, count(*) AS offers
FROM gold.fact_price_observation
WHERE car_key IS NOT NULL AND date_key = (SELECT max(date_key) FROM gold.fact_price_observation)
GROUP BY 1 ORDER BY offers DESC, car_model LIMIT 17;
```

**C7.** Match on **Same part type, same car**: Sellers 13 · Offers 28,825 (unchanged) · Our parts
matched 781 (`parts_type_model`) · Parts 5%+ below 733 (`parts_below_type_model`) · Share 93.9%
(`parts_below_type_model_pct`, 93.854033).

**C8.** Match cleared (eraser icon): the label reads "Match: Both match grades". Our parts matched
935 (`parts`) · Parts 5%+ below 821 (`parts_below`) · Share 87.8% (`parts_below_pct`, 87.807487).
Select **Exact part number** again.

```sql
SELECT coalesce(o.match_grade, 'both') AS grade, o.parts_matched, u.parts_undercut,
       round(u.parts_undercut * 100.0 / nullif(o.parts_matched, 0), 1) AS share_pct
FROM (SELECT match_grade, count(DISTINCT part_key) AS parts_matched FROM gold.fact_price_observation
      WHERE part_key <> 0 AND date_key = (SELECT max(date_key) FROM gold.fact_price_observation)
      GROUP BY ROLLUP (match_grade)) o
JOIN (SELECT match_grade, count(DISTINCT part_no) AS parts_undercut FROM gold.undercut
      GROUP BY ROLLUP (match_grade)) u ON o.match_grade IS NOT DISTINCT FROM u.match_grade;
```

## Page 2: Price gaps

**C9.** Match on **Exact part number**. Cards: Parts measured 61 (`spread_groups_part_number`) ·
Cheapest seller below our price, median part 26.40% (`gap_median_pct_part_number`, 26.4) ·
Dearest seller above the cheapest, median part 38.30% (`spread_median_pct_part_number`, 38.297872).
Both family charts have one bar, **belt**: 26.40% and 38.30% (**SQL only** by family; every part
measured by part number is a belt, so the bar equals the card). The table has 61 rows (one per
measured part), sorted by "Cheapest below our price", highest first. Its first five rows
(**SQL only**, the third query below):

| Part number | Part | Our price | Cheapest seller | Cheapest | Dearest | Gap | Spread |
|---|---|---|---|---|---|---|---|
| EG-2470050D | Belt 6PK1070 for Peugeot 307 | 625.00 | Amazon Egypt | 180.10 | 550.00 | 71.2% | 205.4% |
| EG-C383A19D | Belt 4PK850 for Hyundai Verna | 255.00 | Tawfiqia | 90.00 | 259.92 | 64.7% | 188.8% |
| EG-4FF857FC | Belt 4PK845 for Hyundai Verna | 350.00 | GE Trading | 144.00 | 335.00 | 58.9% | 132.6% |
| EG-C9822077 | Belt 3PK740 for Renault Clio | 387.50 | Zait and Filters | 160.00 | 350.00 | 58.7% | 118.8% |
| EG-B4B10F2D | Belt 6PK1548 for Volkswagen Golf | 460.00 | GE Trading | 223.00 | 460.00 | 51.5% | 106.3% |

Gap is "Cheapest below our price", Spread is "Dearest above the cheapest".

**C10.** Match on **Same part type, same car**. Cards: 676 (`spread_groups_type_model`) · 40.00%
(`gap_median_pct_type_model`) · 90.24% (`spread_median_pct_type_model`, 90.240300). Gap by family
(#7), top to bottom: spark plug 47.65% · filter 42.90% · brake pad 37.50% · wiper 35.15% · belt
27.40%. Spread by family (#8): wiper 141.40% · filter 109.18% · brake pad 98.68% · belt 58.72% ·
spark plug 46.31%. **SQL only** by family for this grade (`numbers.json` splits families over both
grades); brake pad, filter, spark plug and wiper are matched by part type only, so their bars equal
C11's. Spark plug's 47.65% is the average of the two middle parts of 70: it proves MEDIANX averages
the middle pair, as the notebook does.

**C11.** Match cleared. Cards: 737 (`groups_measured`, `spread_groups`) · 38.50%
(`gap_median_pct`) · 83.33% (`spread_median_pct`, 83.333333). Gap by family: spark plug 47.65%
(`gap_median_pct_spark_plug`) · filter 42.90% (`gap_median_pct_filter`) · brake pad 37.50%
(`gap_median_pct_brake_pad`) · wiper 35.15% (`gap_median_pct_wiper`) · belt 27.10%
(`gap_median_pct_belt`). Spread by family: wiper 141.40% (`spread_median_pct_wiper`,
`spread_top_family`) · filter 109.18% (`spread_median_pct_filter`) · brake pad 98.68%
(`spread_median_pct_brake_pad`) · spark plug 46.31% (`spread_median_pct_spark_plug`) · belt 44.25%
(`spread_median_pct_belt`). Hover a bar: Parts Measured belt 125 · brake pad 185 · filter 343
· spark plug 70 · wiper 14 (**SQL only**). Select **Exact part number** again.

```sql
-- Cards: parts measured, median gap and median spread, per grade and both
SELECT coalesce(match_grade, 'both') AS grade, count(*) AS parts_measured,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY gap) AS median_gap_pct,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY spread) AS median_spread_pct
FROM (SELECT part_no, match_grade, max(gap_pct) AS gap, 100 * (max(their_price) / min(their_price) - 1) AS spread
      FROM market GROUP BY part_no, match_grade) t
GROUP BY ROLLUP (match_grade);

-- Family charts, per grade and both
SELECT coalesce(match_grade, 'both') AS grade, family, count(*) AS parts_measured,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY gap) AS median_gap_pct,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY spread) AS median_spread_pct
FROM (SELECT part_no, match_grade, family, max(gap_pct) AS gap, 100 * (max(their_price) / min(their_price) - 1) AS spread
      FROM market GROUP BY part_no, match_grade, family) t
GROUP BY GROUPING SETS ((match_grade, family), (family)) ORDER BY grade, family;

-- The parts table, Exact part number, highest gap first
SELECT m.part_no, p.name, m.our_price, min(m.their_price) AS cheapest_price, max(m.their_price) AS dearest_price,
       max(m.gap_pct) AS gap_pct, round(100 * (max(m.their_price) / min(m.their_price) - 1), 1) AS spread_pct,
       (SELECT string_agg(s.name, ', ' ORDER BY s.name) FROM market x JOIN gold.dim_seller s USING (seller_id)
        WHERE x.part_no = m.part_no AND x.their_price = min(m.their_price)) AS cheapest_seller
FROM market m JOIN gold.dim_part p USING (part_no)
WHERE m.match_grade = 'part_number'
GROUP BY m.part_no, p.name, m.our_price ORDER BY gap_pct DESC, m.part_no;
```

## Page 3: Sellers

Each line: seller, Cheapest share (Cheapest in / Measured parts it sells), Price index. The bars and
the table show the sellers in 5 measured parts or more.

**C12.** Match on **Exact part number** (**SQL only**: `numbers.json` has no seller split by grade):
five sellers. Tawfiqia 58.8% (10 / 17), 0.83 · AutoSpare 49.1% (28 / 57), 0.88 · N Auto Express
27.8% (5 / 18), 0.95 · Zait and Filters 22.9% (11 / 48), 0.98 · GE Trading 22.2% (4 / 18), 0.91.
Amazon Egypt (2 parts) and Pringi (3) are left out by the 5-part filter.

**C13.** Match on **Same part type, same car** (**SQL only**): twelve sellers. Pringi 82.1%
(46 / 56), 0.67 · AutoSpare 55.3% (335 / 606), 0.72 · Tawfiqia 53.1% (94 / 177), 0.67 · GE Trading
30.9% (17 / 55), 0.79 · Zait and Filters 30.2% (121 / 401), 0.80 · Spare Zone 22.2% (2 / 9), 1.14 ·
Amazon Egypt 20.0% (25 / 125), 1.00 · Jumia Egypt 15.4% (4 / 26), 1.00 · YourParts 9.7% (9 / 93),
1.02 · N Auto Express 9.3% (7 / 75), 0.91 · Egy Car Parts 6.8% (24 / 354), 1.10 · Fit and Fix 0.0%
(0 / 7), 1.16. Garageilla (3 parts) is left out.

**C14.** Match cleared: twelve sellers, every number in `numbers.json` (`lead_share_<seller_id>_pct`,
`cheapest_parts_<seller_id>`, `compete_parts_<seller_id>`, `price_index_<seller_id>`). Pringi 81.4%
(48 / 59), 0.67 (`leader`, `leader_share_pct`, `leader_parts`, `leader_price_index`) · AutoSpare
54.8% (363 / 663), 0.73 · Tawfiqia 53.6% (104 / 194), 0.68 · Zait and Filters 29.4% (132 / 449),
0.82 · GE Trading 28.8% (21 / 73), 0.87 · Spare Zone 22.2% (2 / 9), 1.14 · Amazon Egypt 21.3%
(27 / 127), 1.00 · Jumia Egypt 15.4% (4 / 26), 1.00 · N Auto Express 12.9% (12 / 93), 0.93 ·
YourParts 9.7% (9 / 93), 1.02 · Egy Car Parts 6.8% (24 / 354), 1.10 · Fit and Fix 0.0% (0 / 7),
1.16. Garageilla (3 parts: 100.0%, 0.40) is left out. The price index chart, lowest first: Pringi,
Tawfiqia, AutoSpare, Zait and Filters, GE Trading, N Auto Express, Amazon Egypt, Jumia Egypt,
YourParts, Egy Car Parts, Spare Zone, Fit and Fix (Amazon Egypt and Jumia Egypt tie at 1.00). Select **Exact part number** again.

```sql
SELECT coalesce(m.match_grade, 'both') AS grade, s.name, count(*) AS parts_measured,
       count(*) FILTER (WHERE m.their_price = m.lowest) AS cheapest_in,
       round(count(*) FILTER (WHERE m.their_price = m.lowest) * 100.0 / count(*), 1) AS cheapest_share_pct,
       round((percentile_cont(0.5) WITHIN GROUP (ORDER BY m.their_price / m.median_price))::numeric, 2) AS price_index
FROM (SELECT *, min(their_price) OVER (PARTITION BY part_no) AS lowest FROM market) m
JOIN gold.dim_seller s USING (seller_id)
GROUP BY GROUPING SETS ((m.match_grade, s.name), (s.name))
HAVING count(*) >= 5
ORDER BY grade, cheapest_share_pct DESC;
```

## Labels and clicks

**C15.** The label (#2) on every page: "Run week 2026-10-05 · Match: Exact part number" with Exact
part number; "... Match: Same part type, same car" with the other; "... Match: Both match grades"
with the slicer cleared. All three pages change together (the slicer is synced).

**C16.** On Overview, Match on Exact part number, click **AutoSpare** in the seller bar (#9):
Sellers 1 · Offers 9,981 (`offers_autospare`) · Our parts matched 81 · Parts 5%+ below 44 · Share
54.3% (**SQL only**, the query below: the parts AutoSpare has offers for, and those where it is at
least 5% below our price). The car model bar shows AutoSpare's
offers only. Click AutoSpare again to clear.

```sql
SELECT (SELECT count(DISTINCT part_key) FROM gold.fact_price_observation f JOIN gold.dim_seller s USING (seller_key)
        WHERE s.seller_id = 'autospare' AND f.part_key <> 0 AND f.match_grade = 'part_number'
          AND f.date_key = (SELECT max(date_key) FROM gold.fact_price_observation)) AS parts_matched,
       (SELECT count(DISTINCT part_no) FROM gold.undercut
        WHERE seller_id = 'autospare' AND match_grade = 'part_number') AS parts_undercut;
```

**C17.** On Price gaps, Match on Same part type, same car, click **filter** in the gap by family
chart (#7): Parts measured 343 · median gap 42.90% (`gap_median_pct_filter`) · median spread
109.18% (`spread_median_pct_filter`); the spread chart shows filter only and the table 343 rows.
Click it again to clear, then select **Exact part number**.
