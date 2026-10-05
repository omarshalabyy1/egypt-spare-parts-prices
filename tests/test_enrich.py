"""Checks for enrich.py: part type and position, the car a title names, and the part code. Titles
are real ones from the pages kept on 2026-10-05. No network and no warehouse are used."""

import pytest

import enrich


@pytest.mark.parametrize("title, expected", [
    ("فلتر هواء كيا جراند سيراتو 2018 2019 2020 2021 2022 MOBIS", ("air filter", None)),
    ("فلتر تكييف كربون رينو ميجان 2003 2004 2005 2006 2007 2008 2009 ASG", ("cabin filter", None)),
    ("فلتر مكيف الهواء (أوبل جراندلاند 1)", ("cabin filter", None)),  # names air too: cabin wins
    ("فلتر بنزين بالخرطوم نيسان صني N16", ("fuel filter", None)),
    ("Bosch P3079 Car Oil Filter", ("oil filter", None)),
    ("حشو فلتر زيت فتيس نيسان سنترا FEBI", ("filter", None)),  # a gearbox filter is not an engine oil filter
    ("تيل خلفي كيا سبورتاج 2005 2006 2007 2008 2009 2010 FERBE", ("brake pad", "rear")),
    ("تيل امامى اوبل استرا 2010 AUTO TOP", ("brake pad", "front")),
    ("Brake Pads Set Front Skoda Octavia A8 [Rbrake] (Made in Spain) (RB2369)", ("brake pad", "front")),
    ("وسادات الفرامل (مرسيدس بنز B180 (W246))_158200", ("brake pad", None)),
    ("طقم بوجيهات بلاتينيوم كيا كارينز 2014 MOBIS", ("spark plug", None)),
    ("شمعة الإشعال (SEAT Altea)", ("spark plug", None)),
    ("Chloride Gold Car Battery, 12 Volt, 55 Ampere  - DIN55L", ("battery", None)),
    ("Andrew 1000A Copper Car Battery Charging Cable 2.5m", (None, None)),  # a cable, not a battery
    ("سير تكييف BYD F3 5PK1065", ("belt", None)),
    ("بوجيه عاده - لانسر شارك - بوش", ("spark plug", None)),
    ("Lamp Halogen H7 [Zemo] (Made in India) //", ("bulb", None)),
    ("مساحه خلفى - AUDI Q3-Q8 - بوش", ("wiper", None)),
    ("CPC XPL Motor Oil, 20W-50, 1L", ("oil", None)),
    ("اويل سيل فلتر زيت – شيرى نيو تيجو موديل (2014 – 2018)", (None, None)),  # an oil seal
    ("موبينة هيونداي النترا AD", (None, None)),  # an ignition coil: none of our families
    ("طقم تيل فرامل امامي سيراتو", ("brake pad", "front")),  # سير inside سيراتو is not a belt
])
def test_part_type(title, expected):
    assert enrich.part_type(title) == expected


@pytest.mark.parametrize("title, site_car, expected", [
    ("تيل خلفي كيا بيكانتو 2012 2013 2014 2015 2016 2017 2018 LUXSY", None,
     ("kia", "picanto", 2012, 2018, "kia-picanto-2012-2018")),
    ("ماركة بديلة - فلتر هواء كوري | هيونداي النتراAD (2016 - 2020)", "هيونداي النتراAD (2016 - 2020)",
     ("hyundai", "elantra", 2016, 2020, "hyundai-elantra-2016-2020")),
    ("GMفلتر زيت اصلي | شيفروليه نيواوبترا (2014 - 2024)", None,
     ("chevrolet", "optra", 2014, 2024, "chevrolet-optra-2014-2024")),
    ("Hi-Q Front Brake Pads, New Hyundai Elantra (2007-2011)", None,
     ("hyundai", "elantra", 2007, 2011, "hyundai-elantra-2007-2011")),
    ("Cabin AC Air Filter for Renault Duster 2015 High Filtration", None,
     ("renault", "duster", 2015, 2015, "renault-duster-2015-2015")),
    ("فلتر B.F.E زيت نيسان صنى N17", None, ("nissan", "sunny", None, None, "nissan-sunny")),  # chassis code: no years
    ("طقم تيل فرامل امامى – اسبرانزا M11 موديل (2008 – 2015)", "اسبرانزا",
     ("speranza", "m11", 2008, 2015, "speranza-m11-2008-2015")),
    ("طلمبة بنزين مخرج واحد – اسبرانزا تيجو موديل (2009 – 2012) 2000 CC", "اسبرانزا",
     ("speranza", "tiggo", 2009, 2012, "speranza-tiggo-2009-2012")),  # 2000 CC is the engine, not a year
    ("Spark Plug [NGK] (made in Japan) (DCPR7E)", None, (None, None, None, None, None)),  # Spark Plug is no Chevrolet
    ("Elantra Camel HD Air Filter 2007-2011 / Cerato 2009-2013", None, (None, None, None, None, None)),  # two cars
    ("Mahle OIL FILTER FORD CORSA  CHERY LADA", None, ("chery", None, None, None, None)),  # Corsa is no Chery
    ("Oil Filter For Chrysler - Jeep - Mini - Suzuki - Toyota", None, (None, None, None, None, None)),
    ("Bosch P3079 Car Oil Filter", None, (None, None, None, None, None)),  # no car named: none guessed
    ("فلتر هواء بيجو 301", None, ("peugeot", "301", None, None, "peugeot-301")),
    ("301 فلتر هواء", None, (None, None, None, None, None)),  # a bare number is a model only with its make
])
def test_car(title, site_car, expected):
    assert enrich.car(title, site_car) == expected


@pytest.mark.parametrize("part_no, title, code", [
    (None, "سير تكييف BYD F3 5PK1065", "5PK1065"),
    ("1025014GH100", "Generator Belt Original For JAC S2", "1025014GH100"),
    (None, "Belt 6PK1460 [Gates](made in EU)", "6PK1460"),
    ("90915-YZZD4", "Oil Filter For Chrysler - Jeep - Mini - Suzuki - Toyota", "90915YZZD4"),
    ("0 242 129 522", "Spark plug", "0242129522"),  # a Bosch number: digits alone, 10 long
    ("RB2369", "Brake Pads Set Front Skoda Octavia A8", "RB2369"),
    ("67008", "فلتر الوقود (هيونداي فيفا)", None),  # a shop's own number
    ("6479.92", "A/C Filter For Alfa Romeo - Audi - BMW - Other Brands", None),
    ("N17", "Air filter Nissan Sunny", None),  # a chassis code
    ("MG5", "Air filter", None),  # a car model
    ("2018", "Air filter", None),  # a year
    ("10W-40", "Engine oil", None),  # an oil grade
    ("SAE50", "Engine oil", None),
    ("DIN55L", "Battery", None),  # a battery size, made by every maker
])
def test_part_code(part_no, title, code):
    assert enrich.part_code(part_no, title) == code
