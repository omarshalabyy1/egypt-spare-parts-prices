<p align="center">
  <img width="100%" src="docs/header.svg" alt="Egypt spare parts price tracker: every competitor price from Egyptian spare-parts sellers, read in one weekly run.">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10">
  <img src="https://img.shields.io/badge/Apache_Airflow-3-017CEE?style=for-the-badge&logo=apacheairflow&logoColor=white" alt="Apache Airflow 3">
  <img src="https://img.shields.io/badge/PostgreSQL-17-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL 17">
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker Compose">
  <img src="https://img.shields.io/badge/Power_BI-Report-F2C811?style=for-the-badge&logo=powerbi&logoColor=black" alt="Power BI">
</p>

<h2 align="center">Chevrolet Optra spare parts, every Egyptian seller</h2>

<h3 align="center">Every Optra part the Egyptian online sellers list, in one file, cheapest first.</h3>

## The result

**Too few exact part-number matches for this car to compare (<!--n:spread_groups_part_number-->2<!--/n-->).**
<!--n:parts_part_number-->3<!--/n--> Optra parts are sold under the same part number by two sellers or more, and
<!--n:spread_groups_part_number-->2<!--/n--> of them have 3 comparable prices or more at 2 sellers or more; a comparison
here needs 3 such parts. Every number on this page comes from [the notebook](analysis/analysis.ipynb), run with
`car_key: chevrolet-optra` in [config/client.yaml](config/client.yaml).

<!--n:offers-->405<!--/n--> listings from <!--n:sellers-->9<!--/n--> sellers name the Chevrolet Optra in run week
<!--n:run_week-->2026-10-05<!--/n-->; 86 of them state the newer generation, the New Optra.[^1]

## Price list

[analysis/price_list.csv](analysis/price_list.csv) holds every listing for the car, by part type and cheapest first
within each part type (listings with no part type read from the title come last), with the seller, price, stock,
brand, title and link. The first 10 rows:

| Part type | Seller | Price (EGP) | Title |
|---|---|---:|---|
| air filter | GE Trading | 79.00 | Air Filter Chevrolet Optra [High Tech] (Made in China) (96553450) |
| air filter | Tawfiqia | 95.00 | فلتر هواء شيفروليه اوبترا شكل قديم |
| air filter | GE Trading | 99.00 | Air Filter Chevrolet New Optra [Azab] (Made in China) (CH-CH0010) |
| air filter | GE Trading | 114.00 | Air Filter chevrolet Optra [Azab](made in China) |
| air filter | N Auto Express | 165.30 | JPN Air Filter Compatible With Chevrolet Optra |
| air filter | AutoSpare | 170.00 | فلتر هواء شيفروليه اوبترا |
| air filter | AutoSpare | 180.00 | فلتر هواء شيفروليه نيو اوبترا |
| air filter | Zait and Filters | 195.00 | فلتر هواء شيفروليه اوبترا 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 AZAB |
| air filter | Zait and Filters | 200.00 | فلتر هواء شيفروليه اوبترا 2004 2005 2006 2007 2008 2009 2010 2011 2012 2013 2014 HIGH TECH |
| air filter | Zait and Filters | 220.00 | فلتر هواء شيفروليه اوبترا 2004 2005 2006 2007 2008 2009 2010 2011 2012 2013 2014 AZAB |

Listings are grouped by part type only; same-type prices are not like-for-like (a hand audit found 13 of 30 such groups fully clean). Exact part-number matches for this car are too few to compare this week.

## Run it

It runs as on main: see Run it in [main's README](https://github.com/omarshalabyy1/egypt-spare-parts-prices/blob/main/README.md).
This branch differs from main only in `car_key` in [config/client.yaml](config/client.yaml) and in the files the
notebook writes from it.

[^1]: Counted with `SELECT count(*) FILTER (WHERE generation = 'NEW') FROM silver.offer WHERE car_key LIKE 'chevrolet-optra%'`
    after the run of week 2026-10-05.
