# Power BI: build the report step by step

The report reads the gold star of the local warehouse and answers three questions about one weekly
run:

1. **Overview:** what the run read: how many sellers and offers, how many of our parts are matched,
   and how many of them have a seller at least 5% below our price.
2. **Price gaps:** for each part, how far our price sits above the cheapest seller, and how far the
   dearest seller sits above the cheapest, by family and part by part.
3. **Sellers:** how often each seller is the cheapest, and where its prices sit against the
   market's middle price.

"Our price" is a made-up retailer's price: the market's middle price for the part (the median of its
comparable offers). A gap is our price over the cheapest seller's, so a gap above 0 means a seller
is cheaper than us.

One slicer, **Match**, sits on every page and decides which matches the gap and seller numbers use:

- **Exact part number** (the default, `part_number`): the same part code at two sellers or more.
- **Same part type, same car** (`type_model`): the same part type for the same car model, so brands
  mix.
- Cleared: both together, the way the notebook's headline numbers count them.

Same part type, same car is shown for exploration only: a hand audit of 30 random groups found 13
fully clean (seed 20261005); the exact part-number grade was 15 of 15 clean.

A label at the top of every page says which match is shown. The offer counts and the offer charts
always count every offer, matched or not.

The pages read in the run (4,754 in the run of 5 October 2026) are not in the report: gold does not
carry them (they are in bronze), and the report reads gold only.

Everything below is copy and paste. **Start with [`08-build-checklist.md`](08-build-checklist.md)**:
numbered steps from starting the warehouse to the last screenshot, with a check number at each
point. It points to the other files:

| File | What it holds |
|---|---|
| [`01-power-query.md`](01-power-query.md) | The two parameters and eight queries (M code): six load, two stay staging |
| [`02-model.md`](02-model.md) | Tables with grain and keys, the date table, seven relationships, hidden columns, sort, formats, display folders, with the reason for each |
| [`03-measures.dax`](03-measures.dax) | The `_Measures` table and 19 measures, grouped by page |
| [`04-pages.md`](04-pages.md) | Three pages, 25 visuals: type, fields, position and size, settings, slicer sync |
| [`05-theme.json`](05-theme.json) | The theme: **View > Themes > Browse for themes**, pick this file |
| [`06-checks.md`](06-checks.md) | Checks C1 to C17: the numbers every card and chart must show, each with its key in `analysis/numbers.json` and the SQL behind it |
| [`07-interactions.md`](07-interactions.md) | Which visual filters which, per page; filters, drill-through, bookmarks and tooltips |
| [`08-build-checklist.md`](08-build-checklist.md) | The build, step by step |

The theme is the one every portfolio report shares (navy, blue, soft grey page), so the reports look
like one family. The pages name colours by theme slot (Theme colour 1 is the blue), never by hex
code.

Prices are Egyptian pounds (EGP), shown to the piastre with no currency symbol.

The warehouse must be running (`docker compose up -d` in the repo root) while you build or refresh
the report. After each Monday's run, press **Refresh** in Power BI: that is the one click.

When the report is built:

- Save it as `powerbi/spare-parts-prices.pbix`.
- Export one image per page to `powerbi/screenshots/overview.png`, `powerbi/screenshots/price-gaps.png`
  and `powerbi/screenshots/sellers.png`.
- Add the three images to the "Power BI" section of the main README.
