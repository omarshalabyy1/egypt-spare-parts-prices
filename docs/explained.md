# The project explained, from zero

This page explains the whole project in plain words: what it does, what every word means, where every number comes from, and how to talk about it in an interview. You do not need to know databases, Airflow or Power BI to read it.

[← Back to the README](../README.md)

## 1. The project in one minute

A shop sells car spare parts: belts, filters, brake pads, spark plugs. A dozen other shops in Egypt sell the same parts online, and their prices move every week. The shop owner cannot answer simple questions:

- For each of my parts, which competitor is cheaper than me, and by how much?
- How far apart are the cheapest and the dearest seller of the same part?
- Did a competitor cut a price this week, or was it always that low?

This project answers them. Once a week it reads the product pages of 13 Egyptian spare-parts sellers, keeps a copy of every page, checks every price, stores every price with the day it was seen, matches each competitor's part to one of the shop's parts, and compares prices. A Power BI report and an alert email sit on top.

Think of it like a person who walks down a market street every Monday with a notebook. At each stall they write down the price of every belt and filter, with the date. They never rub out an old line. Back at the shop they put the same part from different stalls side by side and circle the stalls that sell it for less than the shop does.

## 2. Words you will meet

| Word | What it means here |
|---|---|
| **EGP** | Egyptian pound, the currency of every price here. "427.00 EGP" is 427 pounds. |
| **Seller** | One competitor website. There are 13, listed in `config/client.yaml`, each with a short id such as `autospare` or `pringi`. |
| **Offer, listing** | One product as one seller sells it: a title, a price, a link. "28,825 prices" means 28,825 offers. |
| **Part, our part** | One part in the shop's own catalogue (`data/input/catalogue.csv`), with an id like `EG-DB4E202C` and "our price". There are 935. |
| **Catalogue** | The shop's list of parts and prices. Here the shop is made up, so `make_catalogue.py` built the catalogue (a CSV file: comma-separated values, one row per line) once from the offers: one part per group of matched offers, priced at the market's middle. A real client brings its own file. |
| **Part number, part code** | The code a part is sold under, such as `6PK2360` (a belt size) or a maker's code like `0242129522`. Two sellers using the same code are selling the same part. |
| **Scraping, scraper** | Reading a website's pages with a program instead of by hand. Each seller has its own small scraper in `scrapers/` that knows where that site puts the title and price. |
| **HTML, JSON, API** | HTML (HyperText Markup Language) is the code of a web page. JSON (JavaScript Object Notation) is a plain text format for data. An API (application programming interface) is a door a site opens for programs; some sellers here give their products as JSON through one. |
| **Sitemap** | A file where a site lists all its pages. Zait and Filters is read through its sitemap, one product page at a time. |
| **robots.txt, pace** | `robots.txt` is a site's file that says what programs may read. The scraper reads it first and never sends more than one request every 3 seconds to a site. |
| **Kept page** | Every page read is saved, compressed (gzipped), under `data/raw/<seller>/<week>/`, with one line per page in `index.jsonl` (the address, the status, the time it was read). The week of 2026-10-05 is committed, so anyone can replay it without visiting a site. |
| **Database, PostgreSQL** | A program that stores tables and answers questions about them. This project uses PostgreSQL (often "Postgres"), called "the warehouse" here. |
| **SQL** | Structured Query Language, the language used to build tables and ask a database questions. The files in `sql/` are SQL. |
| **Schema** | A folder of tables inside the database. There are three: `bronze`, `silver` and `gold`. |
| **Bronze, silver, gold** | The three layers. **Bronze** is the raw pages as read. **Silver** is the parsed, typed and checked offers, the price history and the matches. **Gold** is the clean star the report reads. Each layer only reads the one before it. See [layers.svg](layers.svg). |
| **Check, set aside, quarantine** | Every parsed row is checked before it is stored: a title, a link, an id, a price in EGP of at least 2. A row that fails goes to `silver.quarantine` with its reason. It is kept, never silently dropped. |
| **Placeholder price** | A price under 2 EGP, such as 1.00, which a shop shows to mean "ask us". Set aside. |
| **Price range** | One product card with several prices (`EGP 1,305.00 - EGP 1,485.00`). It is not one price, so it is set aside. |
| **Enrich** | Reading the title to find the part type, the car, the pack and the part code. `enrich.py` does it, in Arabic and English. A title that names nothing gets nothing: never guessed. |
| **Fitment, car_key** | Which car a part fits. `car_key` is the car the title names, written like `chery-arrizo` or `chery-tiggo-2014-2018`. See [fitment.md](fitment.md). |
| **Pack: set or single** | A set (a box of 4 spark plugs) and a single piece are never compared. |
| **Match, match group** | Putting offers that are the same part into one group. |
| **Match grade** | How a group was made. `part_number`: the same part code at two sellers or more. `type_model`: the same part type and car model at two sellers or more (for example "brake pad, front, Hyundai Elantra"); those groups mix brands. |
| **Hand audit** | Groups picked at random and read offer by offer, called clean, mixed or wrong. Part-number groups passed, same-type groups did not, so the README compares part-number groups only. |
| **Comparable** | An offer priced within 3 times its group's median, either way. A price above 3 times or below a third of the median is probably another thing sold under the same words (a bundle, a single clip), so it is left out of the comparisons. |
| **Median** | The middle value when prices are sorted. Used instead of the average so one odd price cannot pull the result. |
| **Our price** | The shop's price for a part. Made up here: the median of the group's comparable prices, not shown out of stock, rounded to 0.50 EGP. |
| **Key part** | The top 20% of parts by number of sellers. Only key parts get the undercut email. There are 187. |
| **Undercut** | A seller at least 5% below our price, not shown out of stock. 5 is `rules.undercut_pct` in `config/client.yaml`. |
| **Price gap** | Our price minus the seller's price, also as a percent of our price. Above 0, we are dearer. |
| **Spread** | For one part: the dearest seller's price over the cheapest seller's, minus one. It says how much shopping around pays. |
| **Measured part** | A part with at least 3 comparable offers, not shown out of stock, from at least 2 sellers. Smaller groups are skipped in the market figures. |
| **In stock** | Whether the seller shows the product as available. Some sites do not say. |
| **Struck-out price** | An old price shown crossed out next to the new one. Counted as "discounted". |
| **Site's own count** | The number of products (or pages) a site says a listing holds, read from the kept page. Set against what the run read, it proves the run read everything. |
| **Run week** | The Monday of the week a run covers, here 2026-10-05. Every price carries it. It is also the **watermark**: a rerun of a week adds nothing twice. |
| **Append-only** | Prices are only ever added. A trigger in `sql/silver.sql` makes any update or delete of the price history fail. |
| **Table, row, column, view** | A table is like a spreadsheet sheet. A view is a saved question that looks like a table but is worked out each time it is read. |
| **Grain** | What one row stands for. The grain of the gold fact is "one offer per run week". |
| **Star schema, fact, dimension** | One big table of events (the **fact**, `fact_price_observation`) in the middle and small lookup tables around it (the **dimensions**: seller, part, date). The standard shape for Power BI. See [data-model.svg](data-model.svg). |
| **Primary key (PK), foreign key (FK), unique key (UK)** | A primary key makes each row unique. A foreign key must point to a row that exists in another table. A unique key here is the **natural key**, the id the data already has (`seller_id`, `part_no`). |
| **Surrogate key** | A made-up number (1, 2, 3) used as the key instead of the natural one. Gold uses them; `part_key` 0 means "none of our parts". |
| **Degenerate dimension** | An id kept in the fact with no table of its own: `listing_key`, the seller's own product id. |
| **Airflow, DAG, task** | Apache Airflow runs the weekly steps on a schedule. A DAG (directed acyclic graph) is the list of steps and their order; each step is a task. The DAG here is `spare_parts_prices`. |
| **Docker, Docker Compose** | Docker runs programs in ready-made boxes called containers. `docker-compose.yml` starts the warehouse and Airflow. |
| **Ports 5450 and 8100** | The "door numbers" of the warehouse (5450) and Airflow's page (8100). Fixed, so two copies of the repo cannot run at once. |
| **`.env`** | A file for secrets (the warehouse password, the Gmail login for the email). Never committed; `.env.example` shows its shape. |
| **`config/client.yaml`** | The settings a client changes: the sellers, the catalogue file, the 5% rule, and an optional car to limit the notebook to. YAML is a simple text format for settings. |
| **Notebook, numbers.json** | `analysis/analysis.ipynb` mixes code, its output and notes. It computes every number in the README, saves them in `analysis/numbers.json`, and writes them into the README between markers like `<!--n:offers-->`. |
| **Power BI** | Microsoft's tool for interactive reports. The `powerbi/` folder rebuilds the report step by step. |

## 3. How it works, file by file

The weekly run, in order (the Airflow task names are in brackets):

| Step | File | What it does |
|---|---|---|
| 0 | `docker-compose.yml`, `.env` | Starts the PostgreSQL warehouse (port 5450) and Airflow (port 8100). |
| 0 | `config/client.yaml`, `config.py` | Hold the settings; `config.py` is the only file that reads them. |
| 1 | `tracker.py` (`load_reference`) + `sql/bronze.sql`, `sql/silver.sql`, `sql/gold.sql` | Creates the schemas, tables and views, then loads the 13 sellers and the 935 catalogue parts. Safe to run again. |
| 2 | `tracker.py` (`fetch_pages`, once per seller, side by side) + `scrape.py` + `scrapers/<seller>.py` | Reads each seller's listing pages, following "next page" links or a sitemap, and keeps each page under `data/raw/`. A page already kept for the week is read from disk, never fetched again. A missing listing page stops the task. |
| 3 | `tracker.py` (`load_silver`) + `scrape.py` + `enrich.py` | Loads the page index into `bronze.page`, parses every kept page, checks each row (bad rows to `silver.quarantine`), reads the part type, car and part code from the title, and saves offers to `silver.offer` and prices to `silver.price_observation`. One transaction: a seller that fails leaves nothing of the week behind. |
| 4 | `tracker.py` (`match`) | Groups the offers (part number first, then part type and car), marks offers priced far off their group as not comparable, and links each grouped offer to a catalogue part in `silver.offer_match`. |
| 5 | `tracker.py` (`build_gold`) | Rebuilds the gold star from silver in full: the seller, part and date dimensions and the fact. Stops if the fact comes out empty. |
| 6 | `tracker.py` (`send_alert`) + the `gold.undercut_alert` view | Emails the key parts a seller cut to 5% or more below our price, or listed new. The first week is the baseline, so it sends nothing. |
| 7 | `analysis/analysis.ipynb` | Reads gold, computes every number in the README, draws the charts in `docs/` and writes the numbers into the README. |
| 8 | `powerbi/` | Step-by-step instructions to build the report, and the numbers each card must show (`06-checks.md`). |

`dags/spare_parts_prices.py` is the Airflow file that runs steps 1 to 6 once a week. `make_catalogue.py` ran once, before all this, to build the made-up catalogue.

### One part, from the web page to the final number

The belt `6PK2360` in the README picture. The figures below come from the kept pages of run week 2026-10-05. The notebook prints the three seller prices and our price (cell 15); the other listings and the two gap percents were worked out for this page by re-reading the kept pages with the repo's own scrapers and match code, without the database.

1. **Collect.** Pringi's shop gives its products as JSON through its API; listing `58474` is "سير مجموعة مقاس 6PK2360 – شيرى نيو تيجو موديل (2014 – 2018)" at 427.00 EGP. Auto Spare's page is HTML; one card shows "سير مجموعة 6pk 2360 شيري اريزو 5" at 500 EGP. GE Trading lists "Belt 6PK2360 [DAYCO](Made In China)" at 739.00 EGP, marked out of stock. Each page is kept gzipped under `data/raw/<seller>/2026-10-05/` and gets a row in `bronze.page`.
2. **Check.** Each row has a title, a link, an id and a price in EGP of 2 or more, so none is set aside.
3. **Enrich.** `enrich.part_code` finds the belt size in each title, so all three get the code `6PK2360`. None says it is a set, so the pack is `single`. The car is read too (`chery-tiggo-2014-2018`, `chery-arrizo`), but it is not needed for a part-number match.
4. **Match.** `6PK2360|single` is sold by two sellers or more, so its offers form one `part_number` group. The group holds 9 listings: Pringi at 427.00 and 446.00; Auto Spare at 500, 790, 790, 800, 800 (one of the 800s out of stock) and 1,350; GE Trading at 739.00. N Auto Express sells a 6PK2360 too, but as a set, and no other seller sells that set, so it is not matched.
5. **Comparable.** The group median counts each (seller, title, price) once, because two Auto Spare listings at 790 and two at 800 share the same title. That leaves 7 prices, and the middle one is 739.00. A comparable price lies between 739 / 3 = 246.33 and 739 × 3 = 2,217, so all 9 listings are comparable.
6. **Our price.** The catalogue row is `EG-DB4E202C`, "Belt 6PK2360 for Chery Arrizo", at **645.00 EGP**. It is the median of the comparable prices not shown out of stock, each (seller, title, price) once: 427, 446, 500, 790, 800, 1,350. Six values, so the median is halfway between the two middle ones: (500 + 790) / 2 = 645.00. That is why our price sits above the two cheapest sellers.
7. **Price gap.** The `gold.price_gap` view keeps one row per seller: its cheapest listing not shown out of stock. Pringi 427.00, Auto Spare 500.00, GE Trading 739.00 (its only listing, out of stock).
8. **Undercut.** 5% below our price is 645 × 0.95 = 612.75. Pringi (427.00) and Auto Spare (500.00) are below it and in stock, so both are in `gold.undercut`. Pringi's gap is (645 − 427) / 645 = 33.8%, Auto Spare's 22.5%. GE Trading is out of stock, so it is left out.
9. **Spread.** In stock, the dearest seller is Auto Spare at 500.00 and the cheapest Pringi at 427.00: 500.00 / 427.00 = 1.171, so **17.1%**.
10. **Alert.** This belt is not a key part, so it never triggers the email. A key part would only trigger it from the second run week, on a price cut or a new offer.

## 4. Every number, explained

The numbers in the README come from the notebook ([`analysis/analysis.ipynb`](../analysis/analysis.ipynb)). The cell numbers below count from 0, the first cell. Some numbers are saved by a cell into `analysis/numbers.json` without being printed; the table says so. Cell 31 writes them all into the README.

### The headline and the result

| Number | What it means | How it is worked out | Where |
|---|---|---|---|
| **Every Monday** | When the run starts. | The DAG runs once a week; each run belongs to the Monday its week ends on (the run week). | `dags/spare_parts_prices.py` |
| **88 of the 154 parts (57.1%)** | Of our parts matched by part number, how many have a seller at least 5% below our price. | Parts in `gold.undercut` with match grade `part_number`, out of all part-number parts. 88 / 154 = 57.1%. The cell prints 88 of 154; the percent is saved to `numbers.json` (`parts_below_part_number_pct`). | notebook cell 25 |
| **5%** | The undercut threshold. | A setting, `rules.undercut_pct` in `config/client.yaml`, read by the `gold.undercut` view. | `config/client.yaml`, `sql/gold.sql` |
| **26.3% less** | How far below our price the cheapest seller is, for the median of those 88 parts. | For each undercut part, the largest gap (the cheapest seller); the median over the 88 part-number parts. The cell prints the figure for all 821 undercut parts (37.5%); 26.3 is the part-number figure saved to `numbers.json` (`undercut_gap_median_pct_part_number`). | notebook cell 25 |
| **38.3% above the cheapest (61 parts)** | For the same part number, how much dearer the dearest seller is than the cheapest, in the median part. | For each measured part: dearest comparable in-stock price / cheapest − 1. Median over the 61 measured part-number parts. The cell prints the figure for all 737 measured parts (83.3%); 38.3 and 61 are saved to `numbers.json` (`spread_median_pct_part_number`, `spread_groups_part_number`). | notebook cell 15 |
| **3 prices or more at 2 sellers or more** | The rule for a measured part. | `MIN_OFFERS, MIN_SELLERS = 3, 2`. 737 of 935 parts pass it. | notebook cells 1 and 12 |
| **58.3% name the car; 90 models of 22 makes** | How many prices say which car they fit. | 16,795 of 28,825 offers have a `car_key`. Models are counted without their years. | notebook cell 23 |
| **Hyundai Elantra (776 prices)** | The car with the most prices. | The model with the most offers. | notebook cell 23 |
| **89.5% of 20,116 in stock** | Where a seller says whether a product is in stock, how many are. | Only sellers that mark both in stock and out of stock count. GE Trading only ever marks "out of stock" (1,177 of its 1,530 offers), so it is left out. | notebook cell 23 |
| **Four sites, 99.8% to 100.0% read** | Proof the run read every product the site says it has. | Offers read / the site's own count. Jumia 1,566 / 1,569 = 99.8%, Tawfiqia 3,628 / 3,629 = 99.97%, Fit and Fix 167 / 167 = 100%; Auto Spare states pages, not products: 669 / 669 pages = 100.0%. | notebook cell 6 |
| **9.1% with a struck-out price** | How many prices are shown with an old price crossed out. | Discounted offers / all 28,825 offers. | notebook cell 19 |
| **1 seller, Pringi, on 100.0%** | Pringi shows a struck-out price on every product. | Sellers whose share of discounted offers is 1. | notebook cell 19 |
| **3.7% set aside** | Rows that failed the check. | 1,094 set aside / 29,919 rows checked (1,094 + 28,825). The cell prints 3.66%; the README rounds to one decimal. | notebook cell 6 |
| **1,052 of 1,094 are GE Trading** | Most set-aside rows come from one seller. | GE Trading: 1,023 with no price shown and 29 with a placeholder price (1,023 + 29 = 1,052). The other 42: Amazon Egypt 38 no price shown, Jumia 3 price range, Zait and Filters 1 placeholder price. | notebook cell 6 |
| **28,825 prices from 13 sellers** | Everything one weekly run reads. | Offers in the gold fact for the latest run week, and the sellers among them. | notebook cell 3 |
| **4,754 pages** | Pages read, each kept on disk. | Rows in `bronze.page` for the run week; all 4,754 are kept. | notebook cell 6 |
| **154 parts: 113 belts, 32 filters, 7 brake pads, 2 wipers** | Our parts matched by part number, by family. | Catalogue parts with match grade `part_number`. 113 + 32 + 7 + 2 = 154. | notebook cell 8 |
| **6PK2360, 17.1%** | The belt in the picture: its dearest in-stock seller over its cheapest. | 500.00 / 427.00 − 1. See the worked example in section 3. | notebook cell 15 |
| **Week ending 2026-10-05** | The run week committed in the repo. | The latest run week in gold. | notebook cell 3 |
| **About 180 minutes** | How long a live week takes: the slowest seller, Zait and Filters. | Its last page's time minus its first, from `index.jsonl`: 179.74 minutes over 3,490 pages, rounded. The sellers run side by side, so the slowest one sets the time. | notebook cell 29 |
| **Ports 5450 and 8100** | Where the warehouse and Airflow listen. | Fixed in `docker-compose.yml`. | `docker-compose.yml` |
| **3 warehouse tests** | Tests that need the database and skip without the password. | Two in `tests/test_gold.py` and one in `tests/test_scrape.py` (`test_save_twice_adds_nothing`). | `tests/` |
| **One request every 3 seconds** | The pace per site. | `MIN_DELAY_S = 3` in `scrape.py`; each seller's `crawl_delay_s` in `config/client.yaml` is 3 too. | `scrape.py` |

### The seller table in the Data section

The prices and rows set aside per seller come from notebook cells 3 and 6. The site's own counts come from cell 6, read from the kept pages: Jumia's "N products found", Tawfiqia's `total_record`, Fit and Fix's `total_count`, and Auto Spare's "page 1 of N". Egy Car Parts states its count only in a file the run does not fetch, so it is not measured. "Not stated" means the site shows no total.

| Seller | Prices | Set aside | Note |
|---|---:|---:|---|
| Auto Spare | 9,981 | 0 | 669 of 669 pages, about 15 products a page |
| Egy Car Parts | 3,832 | 0 | count not read |
| Tawfiqia | 3,628 | 0 | of 3,629 stated: one product not found in gold, and the notebook does not say which |
| Zait and Filters | 3,488 | 1 | read from its sitemap, about one product per page (3,490 pages) |
| Amazon Egypt | 1,718 | 38 | |
| Jumia | 1,566 | 3 | of 1,569 stated: 3 short, and 3 price-range rows were set aside |
| GE Trading | 1,530 | 1,052 | |
| Pringi | 1,308 | 0 | |
| N Auto Express | 1,135 | 0 | |
| Your Parts | 283 | 0 | |
| Fit and Fix | 167 | 0 | of 167 stated |
| Spare Zone | 124 | 0 | |
| Garage ILLA | 65 | 0 | |

The 13 prices add up to 28,825. The notebook prints some names joined up ("AutoSpare", "YourParts", "Garageilla"); they are the same sellers.

### The hand audit

"Did not pass a hand audit of match precision" in the README comes from cell 10. Same-type groups (`type_model`), 30 sampled in each of 3 rounds: 11, 19 and 13 clean, with 4, 2 and 1 wrong. Part-number groups, 15 sampled in each of 3 rounds: 15 clean every time. The bar was 27 clean and 0 wrong of 30, so only part-number groups are shown. The sample seed is 20261005. These are fixed results typed into the cell, not computed from the data.

### Things that can look wrong but are not

- **Our price for the belt (645.00) is above both cheap sellers.** Our price is the median of all in-stock comparable listings, and Auto Spare lists the same belt six times, at 500 to 1,350. Section 3 works it out.
- **3.7% set aside, but 1,094 / 28,825 = 3.8%.** The share is of every row the check saw (29,919), including the ones it set aside.
- **88 of 154 in the README, but 821 of 935 in the notebook.** The README shows part-number groups only. 821 includes the same-type groups, which did not pass the audit.
- **737 measured parts, but 821 parts with an undercut.** Different rules: a measured part needs 3 comparable offers at 2 sellers; the undercut view only needs one seller 5% below our price.
- **Three spreads: 38.3%, 83.3% and 17.1%.** 38.3% is the median of the 61 part-number parts, 83.3% the median of all 737 measured parts, 17.1% one belt.
- **26.3% here, 26.4% in the Power BI pack.** 26.3% is the median gap over the 88 undercut part-number parts (cell 25). 26.4% is the median gap to the cheapest seller over all measured part-number parts, undercut or not (cell 13).
- **GE Trading's 739.00 is in the picture but not in the 17.1%.** It is shown out of stock, and out-of-stock prices are left out.
- **The README says an email goes out when a competitor is cheaper, yet none was sent.** The email covers key parts only, needs a price cut or a new offer, and the first run week is the baseline. With one week loaded, there is nothing to compare.
- **Pringi shows a discount on 100% of its prices.** That says nothing about real discounts, so Pringi is left out of the discount comparison (grey in the chart).

### The diagrams

All diagram numbers are for run week 2026-10-05. The 28,825 and 13 in [header.svg](header.svg) are rewritten by the notebook (cell 31); the other diagrams are drawn by hand and do not change with a new run.

| Number | Where you see it | What it means |
|---|---|---|
| **28,825 prices from 13 sellers** | header.svg | Offers and sellers in the run week (notebook cell 3). |
| **427.00, 500.00, 739.00** | header.svg, one-part.svg | The 6PK2360 belt at Pringi, Auto Spare and GE Trading (notebook cell 15). |
| **0, 250, 500, 750, 1,000 EGP** | one-part.svg | The price axis. |
| **+17.1%, 500.00 ÷ 427.00 = 1.171** | one-part.svg | The belt's spread (notebook cell 15). "One piece" because a set is never compared with a single piece. |
| **01 to 05** | how-it-works.svg | The five steps: collect, check, store, match, report. |
| **13 seller sites, fetch_pages x13** | data-flow.svg | One fetch task per seller in Airflow. |
| **935** | data-flow.svg | Parts in `catalogue.csv` and in `silver.part` (notebook cell 8). |
| **4,754** | data-flow.svg | Rows in `bronze.page` (notebook cell 6). |
| **1,094** | data-flow.svg | Rows in `silver.quarantine` (notebook cell 6). |
| **13** | data-flow.svg, data-model.svg | Rows in `silver.seller` and `gold.dim_seller`. |
| **936** | data-flow.svg, data-model.svg | Rows in `gold.dim_part`: the 935 parts plus `part_key` 0, "not one of our parts". Counted with SQL in `powerbi/06-checks.md` (check C2), not printed by the notebook. |
| **1 row** | data-flow.svg, data-model.svg | Rows in `gold.dim_date`: one day per day observed, and every page of this week was read on 5 October 2026. |
| **28,825 rows** | data-flow.svg, data-model.svg | Rows in `gold.fact_price_observation` (notebook cell 3). |
| **10,312 of the 28,825** | data-flow.svg | Offers matched to one of our parts: 977 by part number + 9,335 by part type and car (notebook cell 8). The rest are products the shop does not sell. |
| **2,708** | data-flow.svg, data-model.svg | Rows in the `gold.price_gap` view: one per part per seller. Counted with SQL in `powerbi/01-power-query.md`, not printed by the notebook. |
| **2,429** | data-model.svg | Price Gap rows Power BI loads: 2,708 minus the 279 shown out of stock (`powerbi/01-power-query.md`, `06-checks.md` check C2). |
| **1,415** | data-flow.svg, data-model.svg | Rows in the `gold.undercut` view. Counted with SQL in `powerbi/01-power-query.md`, not printed by the notebook. The 821 parts behind these rows are in notebook cell 25; the row count itself was not re-checked for this page. |
| **empty** | data-flow.svg, data-model.svg | `undercut_alert` and `price_change` compare a week with the one before, so they stay empty while one week is loaded (notebook cell 27). |
| **2 rows** | data-model.svg | The Match Grade table Power BI adds: `part_number` and `type_model`. |
| **1 and \*** | data-model.svg | One dimension row links to many fact rows. |
| **No count on offer, price_observation, offer_match** | data-flow.svg | They were not counted in the Power BI pack, so the diagram shows none (it says so at the bottom). |
| **1 to 4** | data-flow.svg | The layers: bronze, silver, gold, outputs. |
| **Power BI, three pages** | data-flow.svg | The report's pages: Overview, Price gaps, Sellers (`powerbi/04-pages.md`). |

## 5. What the results mean for the business

- **The shop is undercut on more than half of the parts it can compare exactly.** 88 of 154 part-number parts have a seller at least 5% below our price, and the cheapest seller is a median 26.3% below. Our price here is made up, so the real share depends on the client's own prices, but the method is the same.
- **Shopping around pays.** For the same part number, the dearest seller is a median 38.3% above the cheapest. A customer who checks two shops saves real money, so the shop has to check first.
- **A few sellers set the floor.** Pringi is the cheapest in 81.4% of the 59 measured parts it sells, and Auto Spare is the cheapest in 363 parts (notebook cell 17). Those are the sellers to watch each week.
- **A struck-out price is not a cheap price.** Discounted offers sit at a median price index of 1.02 against 1.00 for undiscounted ones (notebook cell 19): shown as a discount, but priced at the market middle.
- **The data can be trusted.** On the four sites that state a count, the run read 99.8% to 100% of it, and every row that failed the check is kept with its reason.
- **The weekly history is the real value.** One week shows who is cheaper. From the second week the project shows who cut a price, and the email names the key parts at risk that week.

## 6. Interview questions you can expect

**Explain the project in 30 seconds.**
Spare-parts shops in Egypt sell the same parts at very different prices, and a retailer cannot see, part by part, where it is undercut. I built a weekly Airflow pipeline that reads 13 sellers' sites, keeps every page, checks every price, stores the history in PostgreSQL in bronze, silver and gold layers, matches competitor offers to the retailer's parts by part number, and feeds a Power BI report and an alert email. One run read 28,825 prices; 88 of the 154 parts matched by part number had a seller at least 5% below our price.

**Why keep every page you read?**
So the parsing can be rerun without visiting the site again. If a parser had a bug, I fix it and replay the kept pages. It also means a fresh clone gets the same numbers: the week of 2026-10-05 is committed and replays without a single request.

**How do you stop a rerun from adding the same prices twice?**
Each table has a key on the natural id: a price is unique per seller, listing and day, and the load uses `ON CONFLICT DO NOTHING`. The day comes from the page's `index.jsonl` line, never from the clock, so a rerun on the same pages produces the same rows. A test, `test_save_twice_adds_nothing`, saves the same rows twice and checks nothing is added.

**Why is the price history append-only, and how is that enforced?**
Because the point is to see how prices move. If a price could be overwritten, a one-week promotion could not be told apart from a new normal. A trigger on `silver.price_observation` refuses any update or delete, so it is enforced by the database, not by a promise.

**How do you match a competitor's part to yours?**
First by part code: the same code at two sellers or more is the same part. What is left is grouped by part type and car model, with brake pad position, belt function and car generation where the title states them. Sets and single pieces are never mixed. A hand audit showed the part-code groups were clean in all three rounds and the type-and-car groups were not, so the README only compares part-code groups.

**Why medians, and why the 3-times rule?**
Listings are noisy: the same words can sell a full kit or one clip. The median ignores a few odd prices, and an offer above 3 times or below a third of its group's median is flagged as not comparable instead of being deleted. It stays in the data with a flag, so it can be checked.

**How do you know the scraper did not miss products?**
Where a site states its own total, the notebook reads it from the kept page and compares it with what was loaded: 99.8% to 100%. And nothing fails quietly: a missing listing page stops the fetch, pages that parse to nothing stop the load, and an empty gold fact stops the build.

**Silver is loaded week by week, but gold is rebuilt in full every run. Why?**
Silver holds the history, so it only ever adds. Gold is a view of that history for Power BI; at about 29 thousand rows a week, rebuilding it in one transaction is simple and can never leave it half updated. With much more data I would load gold incrementally by run week.

**Why are the views and the 5% rule in SQL, not in Power BI?**
So the rule is written once. The alert, the notebook and Power BI all read `gold.undercut`, and the 5% comes from `config/client.yaml`, set on the database by `load_reference`. Change it in one place and every output changes with it.

**How would you set it up for a real retailer?**
They send their catalogue as one CSV (part number, brand, family, price) and the competitor sites they care about. I put the catalogue in `data/input/`, add the sellers in `config/client.yaml` with a small scraper for any new site, and set the email in `.env`. The rest runs as is, every week, on their machine or hosted.

## 7. Limits, in plain words

- One run week is loaded so far, so price changes and the alert email start with the second week.
- The retailer is made up: our price is the market's middle price. Real numbers need the client's real prices.
- Matching by part type and car is not precise enough yet, so those comparisons are kept out of the README.
- Only 58.3% of prices say which car they fit; the rest cannot be compared by car.
- How deep a discount is cannot be measured: only whether a struck-out price was shown is kept.
- Egy Car Parts' completeness is not measured, because its count is in a file the run does not read.
- When a site changes its page layout, its scraper breaks. The run then fails loudly or sends rows to quarantine, and the scraper must be fixed by hand.
- Prices are the prices shown on the sites. Whether a seller can really deliver at that price is not checked.
