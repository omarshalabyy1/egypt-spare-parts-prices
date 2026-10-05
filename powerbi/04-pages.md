# 4. Pages and visuals

Canvas: 16:9, 1280 × 720 (the default). Set each visual's position and size in **Format > General >
Properties**. `x, y, w, h` are in pixels from the top-left corner. Apply the theme (`05-theme.json`)
first so colours and fonts are already right. Colours are named by theme slot: Theme colour 1 is the
blue, 2 the navy, 3 the light blue, 4 the slate grey.

Rename the pages (double-click the tab) to **Overview**, **Price gaps** and **Sellers**.

Number formats come from each measure's format string (`03-measures.dax`), so no visual needs its own
format. On every card set **Format > Visual > Callout value > Display units: None**, and on every bar
chart **Data labels > Values > Display units: None**, so they show the full number as in
`06-checks.md`. Visuals are listed in build order; the `#` is used in `07-interactions.md`.

The first three visuals are the same on every page: the title, the label that says which match is
shown, and the **Match** slicer (synced, see below).

## Page 1: Overview

What the run read this week, and how many of our parts have a seller at least 5% below our price.

| # | Visual | x, y, w, h | Fields | Settings |
|---|---|---|---|---|
| 1 | Text box | 24, 16, 400, 52 | "What the run read this week" | Font 20, bold |
| 2 | Card | 432, 12, 400, 56 | `[Page Label]` | Category label off. Callout value: font size 12, colour Theme colour 2. Shows "Run week 2026-10-05 · Match: Exact part number" |
| 3 | Slicer | 840, 12, 416, 56 | Field: `Match Grade[Grade]` | Slicer settings > Style: Tile. Selection: **Single select** on, "Select all" off. Header text "Match". Select **Exact part number** before saving (step 36 of `08-build-checklist.md`) |
| 4 | Card | 24, 84, 240, 96 | `[Sellers]` | Category label on, renamed on the visual to "Sellers" |
| 5 | Card | 272, 84, 240, 96 | `[Offers]` | Category label "Offers (every offer, matched or not)" |
| 6 | Card | 520, 84, 240, 96 | `[Parts Matched]` | Category label "Our parts matched" |
| 7 | Card | 768, 84, 240, 96 | `[Parts Undercut]` | Category label "Parts with a seller 5%+ below our price"; callout value colour Theme colour 1 |
| 8 | Card | 1016, 84, 240, 96 | `[Share Undercut]` | Category label "Share of the parts matched" |
| 9 | Clustered bar chart | 24, 196, 612, 508 | Y-axis: `Seller[name]`; X-axis: `[Offers]` | Title "Offers by seller, every offer this week". Sort by Offers, descending. Data labels on. Bars Theme colour 1. X-axis title off |
| 10 | Clustered bar chart | 644, 196, 612, 508 | Y-axis: `Offer[Car model]`; X-axis: `[Offers]` | Title "Offers by car model, the 15 most listed". Filters on this visual: `Car model` **is not blank**, then Filter type **Top N**, Show items Top 15, By value `[Offers]`, **Apply filter**. Sort by Offers, descending. Data labels on. Bars Theme colour 1. X-axis title off |

Cards #4 and #5 and both charts count every offer, so the Match slicer does not change them. Cards
#6 to #8 follow it.

Chart #10 shows 16 bars in the run of 5 October 2026, not 15: Power BI's Top N keeps ties, and the
15th and 16th models (Chevrolet Cruze and Opel Astra) both have 325 offers. The notebook's chart
keeps one of them. Offers whose title names no car (12,030 of 28,825) are left out by the "is not
blank" filter.

## Page 2: Price gaps

For the match in the slicer: how far our price sits above the cheapest seller, and how far the
dearest seller sits above the cheapest, by family and part by part. Only measured parts (3 usable
offers from 2 sellers or more) and comparable prices not shown out of stock count.

| # | Visual | x, y, w, h | Fields | Settings |
|---|---|---|---|---|
| 1 | Text box | 24, 16, 400, 52 | "Our price against the cheapest seller" | Font 20, bold |
| 2 | Card | 432, 12, 400, 56 | `[Page Label]` | Copy page 1 #2 and paste it here |
| 3 | Slicer | 840, 12, 416, 56 | Field: `Match Grade[Grade]` | Copy page 1 #3 and paste it here; choose **Sync** when Power BI asks |
| 4 | Card | 24, 84, 405, 96 | `[Parts Measured]` | Category label "Parts measured (3+ offers, 2+ sellers)" |
| 5 | Card | 437, 84, 405, 96 | `[Median Gap]` | Category label "Our price above the cheapest seller, median part"; callout value colour Theme colour 1 |
| 6 | Card | 850, 84, 406, 96 | `[Median Spread]` | Category label "Dearest seller above the cheapest, median part" |
| 7 | Clustered bar chart | 24, 196, 612, 240 | Y-axis: `Part[family]`; X-axis: `[Median Gap]`; Tooltips: `[Parts Measured]` | Title "Our price above the cheapest seller, median part by family". Sort by Median Gap, descending. Data labels on. Bars Theme colour 1. X-axis title off |
| 8 | Clustered bar chart | 644, 196, 612, 240 | Y-axis: `Part[family]`; X-axis: `[Median Spread]`; Tooltips: `[Parts Measured]` | Title "Dearest seller above the cheapest, median part by family". Sort by Median Spread, descending. Data labels on. Bars Theme colour 4. X-axis title off |
| 9 | Table | 24, 452, 1232, 252 | `Part[part_no]`, `Part[name]`, `[Our Price]`, `[Cheapest Seller]`, `[Cheapest Price]`, `[Dearest Price]`, `[Gap To Cheapest]`, `[Spread]` | Title "Each measured part: our price against the cheapest seller (EGP)". Rename on the visual: part_no "Part number", name "Part", Our Price "Our price", Cheapest Seller "Cheapest seller", Cheapest Price "Cheapest price", Dearest Price "Dearest price", Gap To Cheapest "Our price above the cheapest", Spread "Dearest above the cheapest". Sort by Our price above the cheapest, descending. Conditional formatting > Background color on Gap To Cheapest: Format style Gradient; Minimum: Lowest value, White; Maximum: Highest value, Theme colour 3. Totals off |

In the table, the darker the cell, the further a seller is below our price. The table lists only the
measured parts of the match shown (`Our Price` is blank for the others, so their rows drop out). A
part with two sellers tied at the cheapest price shows both, comma-separated.

With **Exact part number**, both family charts have one bar: every measured part matched by part
number is a belt in the run of 5 October 2026 (check C9).

## Page 3: Sellers

For the match in the slicer: how often each seller is the cheapest in the measured parts it sells,
and where its prices sit against the market's middle price.

| # | Visual | x, y, w, h | Fields | Settings |
|---|---|---|---|---|
| 1 | Text box | 24, 16, 400, 52 | "How often each seller is the cheapest" | Font 20, bold |
| 2 | Card | 432, 12, 400, 56 | `[Page Label]` | Copy page 1 #2 and paste it here |
| 3 | Slicer | 840, 12, 416, 56 | Field: `Match Grade[Grade]` | Copy page 1 #3 and paste it here; choose **Sync** when Power BI asks |
| 4 | Clustered bar chart | 24, 84, 612, 380 | Y-axis: `Seller[name]`; X-axis: `[Cheapest Share]`; Tooltips: `[Cheapest In]`, `[Parts Measured]` | Title "Share of its measured parts where the seller is the cheapest". Filters on this visual: `Parts Measured` **is greater than or equal to** 5, Apply filter. Sort by Cheapest Share, descending. Data labels on. Bars Theme colour 1. X-axis title off |
| 5 | Clustered bar chart | 644, 84, 612, 380 | Y-axis: `Seller[name]`; X-axis: `[Price Index]`; Tooltips: `[Parts Measured]` | Title "Price index: the seller's price over the market's middle price, median part". Filters on this visual: `Parts Measured` is greater than or equal to 5. Sort by Price Index, ascending. Data labels on. Bars Theme colour 4. Analytics pane > X-axis constant line > Add > Value 1; line colour Theme colour 2, style Dashed; Data label on, Text "Name", Name "Market middle price" |
| 6 | Table | 24, 480, 1232, 224 | `Seller[name]`, `[Parts Measured]`, `[Cheapest In]`, `[Cheapest Share]`, `[Price Index]` | Title "Each seller in the measured parts". Filters on this visual: `Parts Measured` is greater than or equal to 5. Rename on the visual: name "Seller", Parts Measured "Measured parts it sells", Cheapest In "Cheapest in", Cheapest Share "Cheapest share", Price Index "Price index". Sort by Cheapest share, descending. Totals off |

A seller in fewer than 5 measured parts is left out of the three visuals, as in the notebook's chart:
one or two parts make a share of 0% or 100% that says nothing. Below 1 on the price index means the
seller's median part sits below the market's middle price; above 1, above it.

## Sync the slicers

**View > Sync slicers**, select the Match slicer, and tick **Sync** and **Visible** on every page:

| Slicer | Overview | Price gaps | Sellers | Why |
|---|---|---|---|---|
| Match (`Match Grade[Grade]`) | yes | yes | yes | One choice of match for the whole report, shown on every page |

To see both matches together (the notebook's headline numbers), clear the slicer with the eraser
icon in its header; the label then says "Both match grades". Select **Exact part number** again
before saving.

## Not used

No drill-through, bookmarks, buttons or tooltip pages, and no page- or report-level filters in the
Filters pane. The match is chosen in a slicer rather than a report-level filter, so it stays visible
on every page. The visual-level filters are listed with each visual above and in
`07-interactions.md`.
