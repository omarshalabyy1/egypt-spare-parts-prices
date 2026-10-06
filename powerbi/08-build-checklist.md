# 8. Build checklist

Follow in order. A **Check** line is a number to verify before going on (all in `06-checks.md`); if
it is off, fix that step first.

## Prepare the warehouse

1. Start Docker Desktop. In the repo folder, if there is no `.env` yet, copy `.env.example` to `.env`
   and set `WAREHOUSE_PASSWORD` to a password of your choice. Then run `docker compose up -d --build`.
2. Open Airflow on port 8100 and switch `spare_parts_prices` on (the toggle left of its
   name). It runs the latest week; a full run takes about three hours (185 minutes on 5 October
   2026), most of it reading Zait and Filters.
3. **Check:** in Airflow the run of `spare_parts_prices` is green (every task, `build_gold`
   included). Then **C1** with the SQL in `06-checks.md`.
4. The numbers in `06-checks.md` are for the run week of 5 October 2026. A later run reads that
   week's prices, so the numbers move: run the notebook (`jupyter lab analysis/analysis.ipynb`, then
   **Run > Run All Cells**; it rewrites `analysis/numbers.json`) and, for every check below, use the
   SQL in `06-checks.md` and the `numbers.json` keys it names instead of the numbers written there.

## Power BI settings

5. Open Power BI Desktop, then **Blank report**.
6. **File > Options and settings > Options > Current file**:
   - **Data load:** untick **Auto date/time**.
   - **Report settings:** tick **Change default visual interaction from cross highlighting to cross
     filtering**.
7. **View > Themes > Browse for themes**, pick `powerbi/05-theme.json`.

## Power Query (`01-power-query.md`)

8. **Home > Transform data**. Create the `WarehouseServer` (`127.0.0.1:5450`) and
   `WarehouseDatabase` (`parts`) parameters.
9. Create the queries in this order, pasting each one's M code: `Seller`, `Offer`, `Part Market`,
   `Part`, `Match Grade`, `Undercut`, `Price Gap`, `Date`. The first asks for credentials: Database,
   user `parts`, the `WAREHOUSE_PASSWORD` from `.env`.
10. Right-click `Part Market` and `Undercut` and untick **Enable load**: they are staging.
11. **Home > Close & apply**. It takes close to a minute: `gold.price_gap` and `gold.undercut` take
    about 19 and 23 seconds to compute.
12. **Check:** if Power BI stops with the error "gold is empty: run the DAG first" (from the `Offer`
    query), gold has no offers: `build_gold` has not run, or is rebuilding gold right now. Wait for
    the DAG run to finish green (step 3), check **C1**, then **Home > Refresh**. The same error on a
    later Refresh means the same thing: never build or refresh on an empty gold.
13. Open **Table view** (second icon on the left) and click each table; the row count is at the
    bottom left.
    **Check C2:** Seller 13 · Part 936 · Date as `gold.dim_date` · Match Grade 2 · Offer 28,825 ·
    Price Gap 2,429.

## Model (`02-model.md`)

14. **Model view**: delete any relationship Power BI made on its own, then create the seven
    relationships in the table, each One to many, Single, Active.
15. Mark `Date` as the date table (column `date`).
16. Hide the columns listed under "Hide columns".
17. Sort `Match Grade[Grade]` by `match_grade`.
18. Set the column formats.

## Measures (`03-measures.dax`)

19. **Home > Enter data**, name the table `_Measures`, **Load**.
20. Paste the 19 measures one by one into `_Measures`, setting each one's format string and display
    folder. Hide the empty column.
21. On a blank page, drop a card with `[Offers]` and one with `[Parts Measured]` (Display units:
    None).
    **Check C3:** 28,825 and 737. Delete both cards.

## Page 1: Overview (`04-pages.md`)

22. Rename the page to **Overview**. Build visuals 1 to 10 in order, with their position and size.
    In the Match slicer (#3), select **Exact part number**.
23. **Check C4:** the label and the five cards.
24. **Check C5:** the seller bars, from AutoSpare down to Garageilla.
25. **Check C6:** the car model bars, 16 of them, from Hyundai Elantra down.
26. **Check C7:** Match on **Same part type, same car**. **Check C8:** clear the slicer (eraser
    icon). Select **Exact part number** again.

## Page 2: Price gaps (`04-pages.md`)

27. Add a page, rename it **Price gaps**. Build visuals 1 to 9 in order. For #2 and #3, copy the
    label and the slicer from Overview (Ctrl+C there, Ctrl+V here) and choose **Sync** when Power BI
    asks whether to sync the slicer.
28. **Check C9:** the cards, the two one-bar family charts, and the table's 61 rows.

## Page 3: Sellers (`04-pages.md`)

29. Add a page, rename it **Sellers**. Build visuals 1 to 6 in order, copying #2 and #3 from
    Overview as in step 27.
30. **Check C12:** five sellers with Exact part number.

## Slicers and interactions

31. **View > Sync slicers**, select the Match slicer: **Sync** and **Visible** ticked on all three
    pages (the table in `04-pages.md`).
32. Set every interaction as in `07-interactions.md`, page by page.
33. **Check C10, C11:** on Price gaps, Match on Same part type, same car, then cleared.
    **Check C13, C14:** the same two on Sellers. **Check C15:** the label's three texts.
34. **Check C16:** on Overview, with Exact part number, click AutoSpare in the seller bar. Click it
    again to clear.
35. **Check C17:** on Price gaps, Match on Same part type, same car, click **filter** in the gap by
    family chart. Click it again to clear.
36. Select **Exact part number** in the Match slicer and leave it selected: the slicer's choice is
    saved with the file, so this is the view the report opens on.

## Save and screenshots

37. **File > Save as** `powerbi/spare-parts-prices.pbix`.
38. Export each page at 1280 × 720 (**File > Export > Export to PDF**, or a screenshot of the page),
    with Exact part number selected and nothing clicked, to `powerbi/screenshots/overview.png`,
    `powerbi/screenshots/price-gaps.png` and `powerbi/screenshots/sellers.png`.
39. In the main `README.md`, replace the comment in the "Power BI" section with the three images.
    Commit and push.
