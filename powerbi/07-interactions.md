# 7. Interactions

## Report setting (once)

**File > Options and settings > Options > Current file > Report settings**: tick **Change default
visual interaction from cross highlighting to cross filtering**.

Why: clicking a bar then filters the other visuals to it instead of greying out part of each bar, so
every card shows the selected seller's or family's real numbers.

## How to set a cell

Select the source visual (the one you click), then **Format > Edit interactions**. Each other visual
shows icons in its top-right corner: **Filter** (funnel) or **None** (circle with a line). Click the
one the table below says. Click **Edit interactions** again to finish.

Numbers are the visual `#` in `04-pages.md`. Text boxes (#1) take no part. Cards are never a source:
clicking a card selects nothing.

## Page 1: Overview

| Source (click) | Label #2 | Match #3 | Cards #4-5 | Cards #6-8 | Seller bar #9 | Car model bar #10 |
|---|---|---|---|---|---|---|
| Match slicer #3 | Filter | | Filter | Filter | Filter | Filter |
| Seller bar #9 | None | None | Filter | Filter | | Filter |
| Car model bar #10 | None | None | Filter | None | Filter | |

Why None on the label and the slicer: a click on a chart should not change which match the page says
it shows, nor shrink the slicer's list.

Why the car model bar does not filter cards #6 to #8: `Price Gap` has no car (a gap belongs to a part
and a seller), so `Parts Undercut` would keep its total while `Parts Matched` shrank, and the share
would mean nothing.

What a click changes:

- **A seller in #9:** the cards show that seller: its offers, the parts it has offers for, the parts
  where it is at least 5% below our price; the car chart shows its offers by car (check C16).
- **A car model in #10:** the offer cards and the seller bar show that car's offers.

## Page 2: Price gaps

| Source (click) | Label #2 | Match #3 | Cards #4-6 | Gap by family #7 | Spread by family #8 | Parts table #9 |
|---|---|---|---|---|---|---|
| Match slicer #3 | Filter | | Filter | Filter | Filter | Filter |
| Gap by family #7 | None | None | Filter | | Filter | Filter |
| Spread by family #8 | None | None | Filter | Filter | | Filter |
| Parts table #9 | None | None | None | None | None | |

What a click changes:

- **A family in #7 or #8:** the cards, the other family chart and the table show that family only
  (check C17).
- **A row in #9:** nothing. The table is for reading.

## Page 3: Sellers

| Source (click) | Label #2 | Match #3 | Cheapest share #4 | Price index #5 | Sellers table #6 |
|---|---|---|---|---|---|
| Match slicer #3 | Filter | | Filter | Filter | Filter |
| Cheapest share #4 | None | None | | Filter | Filter |
| Price index #5 | None | None | Filter | | Filter |
| Sellers table #6 | None | None | None | None | |

What a click changes:

- **A seller in #4 or #5:** the other chart and the table show that seller only.
- **A row in #6:** nothing.

The slicer's "Filter" on the label (#2) is what makes the label follow the match.

## Filters by level

| Level | Filter | Why |
|---|---|---|
| Report | none | The match is a synced slicer, so it is visible on every page instead of hidden in the Filters pane |
| Page | none | Every page shows the whole run week |
| Visual: Overview #10 | `Offer[Car model]` is not blank; Top N 15 by `[Offers]` | The 15 most listed models; offers that name no car are not a model (Top N keeps ties: 16 bars in the run of 5 October 2026) |
| Visual: Sellers #4, #5, #6 | `[Parts Measured]` is greater than or equal to 5 | A seller in fewer than 5 measured parts gives a share of 0% or 100% that says nothing, as in the notebook's chart |

"Latest run week only" and "not shown out of stock" are applied in Power Query (`Offer`, `Price Gap`),
where a filter cannot be cleared by accident.

## Not used

- Drill-through pages: none. The parts table on page 2 already shows each part's cheapest seller.
- Bookmarks and buttons: none. The Match slicer is the one choice the reader makes.
- Tooltip pages: none. The family charts and the seller charts use the default tooltip with
  `Parts Measured` (and `Cheapest In` on Sellers #4) added to their Tooltips well, so each bar says
  how many parts it rests on.
