"""What a listing's title says about the part, in plain dictionaries: the part type (with brake-pad
position), the car it fits (make, model, years) and a part code to match on. Arabic and English.
A title that names nothing stays None: never guessed."""

import re

# --- Text ---------------------------------------------------------------------------------------

def norm(text):
    """Lower case, one spelling per Arabic letter (أإآ -> ا, ى -> ي, ة -> ه, no diacritics), and a
    space wherever Arabic touches Latin letters or digits ('النتراAD' -> 'النترا ad')."""
    text = re.sub(r"[\u064B-\u0652\u0640]", "", (text or "").lower())
    text = text.translate(str.maketrans("أإآٱىة", "اااايه"))
    return re.sub(r"(?<=[\u0600-\u06FF])(?=[a-z0-9])|(?<=[a-z0-9])(?=[\u0600-\u06FF])", " ", text)


def has(text, words):
    """Whether the normalised text holds one of the words (or phrases) as a whole word, also with a
    leading و ("and") or ال ("the"): وبليه and البليه are بليه."""
    return any(re.search(rf"(?<!\w)و?(?:ال)?(?:{w})(?!\w)", text) for w in words)


# --- Part type ----------------------------------------------------------------------------------

# Checked in this order; the first type whose word is in the title wins, unless one of its "not" words is.
PART_TYPES = (
    ("filter", ("فلتر", "فلاتر", "filter", "filters"), ("سيل", "seal", "مفتاح", "wrench", "غطاء", "cap")),
    # Drum-brake shoes are their own type: "تيل خلفي قباقيب" names pads (تيل) but sells shoes.
    ("brake shoe", ("قباقيب", "قبقاب", "brake shoe", "brake shoes", "shoe", "shoes"),
     ("طنابير", "طنبور", "drum", "drums")),  # brake drums are not shoes
    ("brake pad", ("تيل", "فحمات", "وسادات الفرامل", "وسادات فرامل", "brake pad", "brake pads", "pads"),
     ("حساس", "sensor", "cover", "غطاء", "pedal", "دواسه", "wrench", "مفتاح", "طنابير", "طنبور")),  # accessories, tools, discs
    ("spark plug", ("بوجي", "بوجيه", "بوجيهات", "بواجي", "شمعه الاشعال", "شمعات الاشعال", "spark plug", "spark plugs"),
     ("سلك", "بسلك", "سلوك", "موبينه", "lead", "leads", "cable", "cables", "wire", "wires")),  # leads and coils
    ("battery", ("بطاريه", "بطارية", "بطاريات", "battery"),
     ("كابل", "شاحن", "شحن", "دينمو", "دينامو", "cable", "charger", "inverter", "tester", "clamp", "terminal", "jump",
      "starter")),  # what charges or starts from a battery
    ("belt", ("سير", "سيور", "belt", "belts", r"\d{1,2} ?pk ?\d{3,4}"),
     ("clamp", "gt2", "بكره", "بكرات", "شداد", "شداده", "بلي", "بليه", "بالبليه", "رولمان", "جنزير", "pulley", "tensioner",
      "bearing", "chain", "idler")),  # the belt's pulley, tensioner or bearing, or a timing chain
    ("wiper", ("مساحه", "مساحات", "ريش", "ريشه", "wiper", "wipers"), ("موتور", "motor", "ذراع", "arm", "cap")),
    ("bulb", ("لمبه", "لمبات", "bulb", "bulbs", "lamp"), ()),
    ("oil", ("زيت", "زيوت", "oil", "oils"),
     ("سيل", "seal", "طلمبه", "pump", "حساس", "sensor", "غطاء", "cover", "كارتير", "مبرد", "cooler", "خرطوم")),
)
# A filter's kind, checked in this order (an air-conditioning filter names air too).
FILTER_KINDS = (
    ("cabin filter", ("تكييف", "تكيف", "مكيف", "التكييف", "cabin", "a/c", "ac", "air condition", "air conditioning", "pollen")),
    ("fuel filter", ("بنزين", "جاز", "سولار", "ديزل", "وقود", "الوقود", "fuel", "diesel", "petrol", "gasoline")),
    ("oil filter", ("زيت", "الزيت", "oil")),
    ("air filter", ("هواء", "الهواء", "air")),
)
GEARBOX = ("فتيس", "الفتيس", "ناقل الحركه", "transmission", "gearbox", "atf")
# What a belt drives: the camshaft ('timing') or the alternator, air conditioning or power steering
# ('drive', the ribbed PK belts).
BELT_FUNCTIONS = (
    ("timing", ("كاتينه", "تايمنج", "timing", "cam", "camshaft")),
    ("drive", ("مجموعه", "دينامو", "تكييف", "تكيف", "باور", "power steering", "alternator", "a/c", "ac",
               "serpentine", "v-ribbed", "v ribbed", "poly v", "pk", r"\d{1,2} ?pk ?\d{3,4}")),
)


def belt_function(title):
    """'timing' or 'drive' for a belt whose title says which, None when it names neither or both."""
    text = norm(title)
    named = [name for name, words in BELT_FUNCTIONS if has(text, words)]
    return named[0] if len(named) == 1 else None


# Words that make a listing a set of several pieces (a set of 4 plugs), not one piece. Not مجموعه:
# "سير مجموعه" is a kind of belt.
SET_WORDS = ("طقم", "الطقم", "اطقم", "set", "sets", "kit", "pair", "زوج", r"عدد ?[2-9]", r"[2-9]\d? ?(pcs|pieces|قطع)",
             r"x ?[2-9]", r"[2-9] ?x")


def part_type(title):
    """(part type, position, pack): ('brake pad', 'front', 'set'), ('oil filter', None, 'single'),
    or (None, None, pack) when no type word matches. A filter that does not say its kind (or is a
    gearbox filter) is plain 'filter'. pack is 'set' when the title says it is several pieces."""
    text = norm(title)
    pack = "set" if has(text, SET_WORDS) else "single"
    for name, words, nots in PART_TYPES:
        if has(text, words) and not has(text, nots):
            if name == "filter":
                if has(text, GEARBOX):
                    return "filter", None, pack
                return next((kind for kind, w in FILTER_KINDS if has(text, w)), "filter"), None, pack
            if name == "brake pad":  # an axle set is the normal unit: a pad is never a 'set'
                front, rear = has(text, ("امامي", "اماميه", "front")), has(text, ("خلفي", "خلفيه", "rear"))
                return name, "front" if front and not rear else "rear" if rear and not front else None, "single"
            if name == "brake shoe":  # the same: shoes come per axle
                return name, None, "single"
            return name, None, pack
    return None, None, pack


# --- Car ----------------------------------------------------------------------------------------

# make -> its spellings. Normalised text, so شيفرولية is written شيفروليه.
MAKES = {
    "hyundai": ("هيونداي", "هيوانداي", "هيونداى", "hyundai"),
    "chevrolet": ("شيفروليه", "شيفروليت", "شيفرولي", "شفروليه", "شفرليه", "chevrolet", "chevy"),
    "nissan": ("نيسان", "nissan"),
    "kia": ("كيا", "kia"),
    "toyota": ("تويوتا", "toyota"),
    "renault": ("رينو", "renault"),
    "fiat": ("فيات", "fiat"),
    "mg": ("ام جي", "امجي", "mg"),
    "chery": ("شيري", "chery"),
    "speranza": ("اسبرانزا", "speranza"),
    "mitsubishi": ("ميتسوبيشي", "متسوبيشي", "mitsubishi"),
    "skoda": ("سكودا", "skoda"),
    "peugeot": ("بيجو", "peugeot"),
    "byd": ("بي واي دي", "byd"),
    "geely": ("جيلي", "geely"),
    "daewoo": ("دايو", "دايوو", "daewoo"),
    "opel": ("اوبل", "opel"),
    "seat": ("سيات", "seat"),
    "suzuki": ("سوزوكي", "suzuki"),
    "honda": ("هوندا", "honda"),
    "mazda": ("مازدا", "mazda"),
    "volkswagen": ("فولكس", "فولكس فاجن", "volkswagen", "vw"),
    "jeep": ("جيب", "jeep"),
}
# (make, model) -> its spellings. A model written as a bare number (Fiat 128, Peugeot 301) counts
# only when its make is named too; so does a model two makes share (Tiggo: Chery and Speranza).
MODELS = {
    ("hyundai", "elantra"): ("النترا", "الانترا", "elantra"),
    ("hyundai", "verna"): ("فيرنا", "verna"),
    ("hyundai", "accent"): ("اكسنت", "اكسينت", "accent"),
    ("hyundai", "tucson"): ("توسان", "tucson"),
    ("hyundai", "matrix"): ("ماتريكس", "matrix"),
    ("chevrolet", "optra"): ("اوبترا", "نيو اوبترا", "نيواوبترا", "optra"),
    ("chevrolet", "aveo"): ("افيو", "aveo"),
    ("chevrolet", "lanos"): ("لانوس", "lanos"),
    ("chevrolet", "cruze"): ("كروز", "cruze"),
    ("nissan", "sunny"): ("صني", "سني", "sunny"),
    ("nissan", "sentra"): ("سنترا", "سينترا", "sentra"),
    ("nissan", "qashqai"): ("قشقاي", "قاشقاي", "qashqai"),
    ("kia", "cerato"): ("سيراتو", "cerato"),
    ("kia", "rio"): ("ريو", "rio"),
    ("kia", "sportage"): ("سبورتاج", "sportage"),
    ("kia", "picanto"): ("بيكانتو", "picanto"),
    ("kia", "carens"): ("كارينز", "carens"),
    ("toyota", "corolla"): ("كورولا", "كرولا", "corolla"),
    ("toyota", "yaris"): ("ياريس", "يارس", "yaris"),
    ("renault", "logan"): ("لوجان", "logan"),
    ("renault", "megane"): ("ميجان", "megane"),
    ("renault", "sandero"): ("سانديرو", "sandero"),
    ("renault", "duster"): ("داستر", "duster"),
    ("renault", "clio"): ("كليو", "clio"),
    ("fiat", "tipo"): ("تيبو", "tipo"),
    ("fiat", "128"): ("128",),
    ("fiat", "punto"): ("بونتو", "punto"),
    ("mg", "mg5"): ("mg5", "mg 5"),
    ("mg", "zs"): ("zs",),
    ("mg", "rx5"): ("rx5", "rx 5"),
    ("chery", "tiggo"): ("تيجو", "tiggo"),
    ("chery", "arrizo"): ("اريزو", "arrizo"),
    ("speranza", "tiggo"): ("تيجو", "tiggo"),
    ("speranza", "arrizo"): ("اريزو", "arrizo"),
    ("speranza", "a113"): ("a113",),
    ("speranza", "a516"): ("a516",),
    ("mitsubishi", "lancer"): ("لانسر", "lancer"),
    ("skoda", "octavia"): ("اوكتافيا", "octavia"),
    ("peugeot", "301"): ("301",),
    ("peugeot", "3008"): ("3008",),
    ("byd", "f3"): ("f3",),
    ("geely", "emgrand"): ("امجراند", "emgrand"),
    ("daewoo", "nubira"): ("نوبيرا", "nubira"),
    ("opel", "astra"): ("استرا", "astra"),
    ("seat", "leon"): ("ليون", "leon"),
    ("seat", "ibiza"): ("ابيزا", "ibiza"),
    ("suzuki", "swift"): ("سويفت", "swift"),
    ("suzuki", "ciaz"): ("سياز", "ciaz"),
    ("honda", "civic"): ("سيفيك", "civic"),
    # Added from the titles of run week 2026-10-05: the models named 40 times or more.
    ("hyundai", "getz"): ("جيتز", "getz"),
    ("hyundai", "i10"): ("i10",),
    ("hyundai", "grand i10"): ("grand i10", "جراند i10"),  # its own model, not the i10
    ("kia", "grand cerato"): ("grand cerato", "جراند سيراتو"),  # its own model, not the Cerato
    ("hyundai", "i30"): ("i30",),
    ("hyundai", "ix35"): ("ix35",),
    ("hyundai", "creta"): ("كريتا", "creta"),
    ("kia", "soul"): ("سول", "soul"),
    ("kia", "ceed"): ("سييد", "ceed"),
    ("chery", "envy"): ("انفي", "envy"),
    ("speranza", "m11"): ("m11",),
    ("speranza", "a620"): ("a620",),
    ("renault", "fluence"): ("فلوانس", "fluence"),
    ("renault", "kadjar"): ("كادجار", "kadjar"),
    ("renault", "captur"): ("كابتشر", "captur"),
    ("renault", "stepway"): ("ستيبواي", "stepway"),
    ("nissan", "tiida"): ("تيدا", "tiida"),
    ("nissan", "juke"): ("جوك", "juke"),
    ("chevrolet", "spark"): ("سبارك", "spark"),
    ("chevrolet", "captiva"): ("كابتيفا", "captiva"),
    ("opel", "insignia"): ("انسيجنيا", "انسيجينا", "insignia"),
    ("opel", "vectra"): ("فيكترا", "vectra"),
    ("opel", "corsa"): ("كورسا", "corsa"),
    ("volkswagen", "passat"): ("باسات", "passat"),
    ("volkswagen", "jetta"): ("جيتا", "jetta"),
    ("volkswagen", "golf"): ("جولف", "golf"),
    ("volkswagen", "polo"): ("بولو", "polo"),
    ("seat", "toledo"): ("توليدو", "toledo"),
    ("skoda", "rapid"): ("رابيد", "rapid"),
    ("skoda", "superb"): ("سوبيرب", "superb"),
    ("skoda", "kodiaq"): ("كودياك", "kodiaq"),
    ("skoda", "fabia"): ("فابيا", "fabia"),
    ("mg", "hs"): ("hs",),
    ("mg", "mg6"): ("mg6", "mg 6"),
    ("byd", "l3"): ("l3",),
    ("mazda", "3"): ("3",),  # Peugeot 2008 is left out: it reads as a year
    ("peugeot", "307"): ("307",),
    ("peugeot", "308"): ("308",),
    ("peugeot", "508"): ("508",),
    ("peugeot", "5008"): ("5008",),
    ("daewoo", "matiz"): ("ماتيز", "matiz"),
}
# Models that count only when their make is named too: bare numbers (Fiat 128, Peugeot 301), a
# name two makes share (Tiggo: Chery and Speranza), and a name that is also an English word
# ("Spark Plug", "Matrix LED") or an oil's brand (Cruze oil).
NEEDS_MAKE = ({m for (_, m) in MODELS if m.isdigit() or sum(1 for (_, n) in MODELS if n == m) > 1}
              | {"spark", "rapid", "matrix", "cruze"})
# A year stands alone: never inside a part code (28113-F2000) and never an engine size (2000 CC).
YEAR = r"(?<![\w.])(19[89]\d|20[0-3]\d)(?![\w.])(?!\s*(?:cc|سي ?سي))"


def car(title, site_car=None):
    """(make, model, year_from, year_to, car_key) from the title and the car the site states; any
    of them None when not said. A model whose make is not the make named is dropped. Two different
    models named: no model (and a make only if one make is named). Years are kept only with a
    model: the lowest and highest year written."""
    text = re.sub(r"spark ?plugs?", " ", norm(f"{title} {site_car or ''}"))  # "Spark Plug" is no Chevrolet Spark
    makes = {m for m, words in MAKES.items() if has(text, words)}
    models = {(make, model) for (make, model), words in MODELS.items() if has(text, words)
              and (make in makes or (not makes and model not in NEEDS_MAKE))}
    # "Grand i10" and "Grand Cerato" also name the i10 and the Cerato; "Sandero Stepway" also names
    # the Stepway: the longer name is the car.
    models -= {(make, model) for make, model in models
               if any(m == make and n != model and n.endswith(f" {model}") for m, n in models)}
    if {("renault", "sandero"), ("renault", "stepway")} <= models:
        models.discard(("renault", "stepway"))
    if len(models) != 1:
        named = makes | {make for make, _ in models}
        return (named.pop() if len(named) == 1 else None), None, None, None, None
    (make, model), = models
    years = sorted(int(y) for y in re.findall(YEAR, text))
    year_from, year_to = (years[0], years[-1]) if years else (None, None)
    key = f"{make}-{model}" + (f"-{year_from}-{year_to}" if years else "")
    return make, model, year_from, year_to, key


# The generations a title names, for the models whose generations differ in their parts: the
# tokens the titles of 2026-10-05 use. A title naming no generation, or two, gets none.
GENERATIONS = {
    "sunny": {"N16": (r"n ?-?16", "16 ?n"), "N17": (r"n ?-?17", "17 ?n"), "N18": (r"n ?-?18", "18 ?n")},
    "elantra": {"XD": ("xd",), "HD": ("hd",), "MD": ("md", "ام دي"), "AD": ("ad",), "CN7": ("cn7",)},
    "accent": {"RB": ("rb",), "HC": ("hc", "hci")},
    "cerato": {"LD": ("ld",), "TD": ("td",), "K3": ("k3",)},
    "logan": {"NEW": ("نيو لوجان", "new logan")},
    "optra": {"NEW": ("نيو اوبترا", "نيواوبترا", "new optra")},
    "lancer": {"PUMA": ("بومه", "بوما", "puma"), "SHARK": ("شارك", "قرش", "shark"), "CRYSTAL": ("كريستاله",),
               "EX": ("لانسر ex", "lancer ex")},
    "sandero": {"2013+": ("نيو سانديرو", "new sandero"), "STEPWAY": ("ستيب واي", "ستيبواي", "stepway")},
    "megane": {"2": ("ميجان 2", "megane 2"), "3": ("ميجان 3", "megane 3"), "4": ("ميجان 4", "megane 4")},
    "5008": {"I": (r"5008 \(?i",), "II": (r"5008 \(?ii",)},
    "passat": {"B5": ("b5",), "B6": ("b6",), "B7": ("b7",), "B8": ("b8",)},
}
# Generations told apart only by the years a title states: (label, first year, last year).
YEAR_GENERATIONS = {
    "picanto": (("2004-2011", 2004, 2011), ("2012-2018", 2012, 2018), ("2017+", 2017, 9999)),
    "sandero": (("2008-2012", 2008, 2012), ("2013+", 2013, 9999)),
}


def generation(title, site_car, model, year_from=None, year_to=None):
    """The generation the title names for its model ('N17', 'MD', 'PUMA'), else the one its stated
    years fall in (Picanto 2012-2018), or None."""
    text = norm(f"{title} {site_car or ''}")
    named = [code for code, words in GENERATIONS.get(model, {}).items() if has(text, words)]
    if named:
        return named[0] if len(named) == 1 else None
    if year_from:
        return next((label for label, first, last in YEAR_GENERATIONS.get(model, ())
                     if first <= year_from and year_to <= last), None)
    return None


# --- Part code ----------------------------------------------------------------------------------

BELT_SIZE = r"(?<![a-z0-9])(\d{1,2}) ?pk ?(\d{3,4})(?![0-9])"
# An oil grade or a battery size is not a part's code. Car models, chassis codes (N17, MG5, A516)
# and years are shorter than the 5 characters a code needs.
NOT_CODES = (r"(SAE)?\d{1,2}W\d{2}", r"SAE\d{2,3}", r"(DIN|TD|NS|N|AGM)\d{2,3}[LR]?")


def part_code(part_no, title):
    """The code to match on, upper case without spaces, dashes, dots or slashes: a belt size in the
    title (6PK1460), else the seller's part number when it looks like a maker's code: letters and
    digits, 5 to 20 long, or digits alone 8 or more long (Bosch 0242129522). Short shop numbers,
    car models, years, oil grades and battery sizes are not codes."""
    belt = re.search(BELT_SIZE, norm(title))
    if belt:
        return f"{belt.group(1)}PK{belt.group(2)}"
    code = re.sub(r"[\s\-./]", "", (part_no or "").upper())
    if not re.fullmatch(r"[A-Z0-9]{5,20}", code) or any(re.fullmatch(p, code) for p in NOT_CODES):
        return None
    if code.isdigit():
        return code if len(code) >= 8 else None
    return code if re.search(r"[A-Z]", code) and re.search(r"\d", code) else None
