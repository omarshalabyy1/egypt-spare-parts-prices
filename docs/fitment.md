# Fitment: how each seller says which car a part fits

`enrich.car` reads the make, model and years from the title (and from the car the site states, for
Pringi and Your Parts), in Arabic and English, against the dictionary in [enrich.py](../enrich.py).
A title that names no car, or names two different models, gets no `car_key`: never guessed. Years
come only from the title (`(2014 - 2024)`, `2021-2024`, `2012 2013 2014`); a chassis code such as
N17 or AD is ignored (the model name beside it is what matches) and never turned into years.

Counts: offers with a `car_key` out of the seller's offers in silver, run week 2026-10-05.

| Seller | How it states fitment | car_key |
|---|---|---|
| Zait and Filters | Arabic make, model and every model year in the title (`كيا بيكانتو 2012 2013 ... 2018`) | 3,458 of 3,488 |
| Auto Spare | Arabic make and model in the title, often a chassis code (`النترا MD`, `صني N17`), rarely years | 7,668 of 9,981 |
| Pringi | The site's own car field (its "brand" is the car make) and `model موديل (from – to)` in the title | 1,267 of 1,308 |
| Tawfiqia | Arabic make and model in the title, sometimes years (`2004 / 2013`) | 1,782 of 3,628 |
| Your Parts | The site's car field `make model (from - to)`, appended to the title | 139 of 283 |
| GE Trading | English make, model and chassis code after the part name; several cars joined by `/` | 540 of 1,530 |
| Egy Car Parts | Arabic make and model in brackets at the end of the title, no years; mostly European models outside the dictionary | 1,382 of 3,832 |
| N Auto Express | English `Compatible With Make - Make - Make`: usually several makes, a model only sometimes | 197 of 1,135 |
| Amazon Egypt | English free text (`for Hyundai Verna`), often several cars or none | 291 of 1,718 |
| Jumia Egypt | English free text; mostly lights and oils that name no car | 42 of 1,566 |
| Spare Zone | A model without its make (`انسيجنيا`, `IBIZA 2008`); wipers, plugs and oils | 17 of 124 |
| Fit and Fix | Batteries and oils name no car; brake pads name `Hyundai Elantra (2007-2011)` | 10 of 167 |
| Garage ILLA | Oils and batteries name no car; a few filters name the car in Arabic | 4 of 65 |
| All sellers | | 16,797 of 28,825 |
