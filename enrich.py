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
    """Whether the normalised text holds one of the words (or phrases) as a whole word."""
    return any(re.search(rf"(?<!\w){w}(?!\w)", text) for w in words)


# --- Part type ----------------------------------------------------------------------------------

# Checked in this order; the first type whose word is in the title wins, unless one of its "not" words is.
PART_TYPES = (
    ("filter", ("فلتر", "فلاتر", "filter", "filters"), ("سيل", "seal", "مفتاح", "wrench", "غطاء", "cap")),
    ("brake pad", ("تيل", "فحمات", "وسادات الفرامل", "وسادات فرامل", "brake pad", "brake pads", "pads"),
     ("حساس", "sensor")),
    ("spark plug", ("بوجي", "بوجيه", "بوجيهات", "بواجي", "شمعه الاشعال", "شمعات الاشعال", "spark plug", "spark plugs"), ()),
    ("battery", ("بطاريه", "بطارية", "بطاريات", "battery"),
     ("كابل", "شاحن", "cable", "charger", "inverter", "tester", "clamp", "terminal", "jump", "starter")),
    ("belt", ("سير", "سيور", "belt", "belts", r"\d{1,2} ?pk ?\d{3,4}"), ("clamp", "gt2")),
    ("wiper", ("مساحه", "مساحات", "ريش", "ريشه", "wiper", "wipers"), ("موتور", "motor", "ذراع", "arm", "cap")),
    ("bulb", ("لمبه", "لمبات", "bulb", "bulbs", "lamp"), ()),
    ("oil", ("زيت", "زيوت", "oil", "oils"),
     ("سيل", "seal", "طلمبه", "pump", "حساس", "sensor", "غطاء", "cover", "كارتير", "مبرد", "cooler", "خرطوم")),
)
# A filter's kind, checked in this order (an air-conditioning filter names air too).
FILTER_KINDS = (
    ("cabin filter", ("تكييف", "مكيف", "التكييف", "cabin", "a/c", "ac", "air condition", "air conditioning", "pollen")),
    ("fuel filter", ("بنزين", "جاز", "سولار", "ديزل", "وقود", "الوقود", "fuel", "diesel", "petrol", "gasoline")),
    ("oil filter", ("زيت", "الزيت", "oil")),
    ("air filter", ("هواء", "الهواء", "air")),
)
GEARBOX = ("فتيس", "الفتيس", "ناقل الحركه", "transmission", "gearbox", "atf")
# Words that make a listing a set of several pieces (a set of 4 plugs), not one piece. Not مجموعه:
# "سير مجموعه" is a kind of belt.
SET_WORDS = ("طقم", "اطقم", "set", "sets", "kit", "pair", "زوج", r"عدد ?[2-9]", r"[2-9]\d? ?(pcs|pieces|قطع)",
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
            if name == "brake pad":
                front, rear = has(text, ("امامي", "اماميه", "front")), has(text, ("خلفي", "خلفيه", "rear"))
                return name, "front" if front and not rear else "rear" if rear and not front else None, pack
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
YEAR = r"(?<![\d.])(19[89]\d|20[0-3]\d)(?![\d.])(?!\s*(?:cc|سي ?سي))"


def car(title, site_car=None):
    """(make, model, year_from, year_to, car_key) from the title and the car the site states; any
    of them None when not said. A model whose make is not the make named is dropped. Two different
    models named: no model (and a make only if one make is named). Years are kept only with a
    model: the lowest and highest year written."""
    text = norm(f"{title} {site_car or ''}")
    makes = {m for m, words in MAKES.items() if has(text, words)}
    models = {(make, model) for (make, model), words in MODELS.items() if has(text, words)
              and (make in makes or (not makes and model not in NEEDS_MAKE))}
    if len(models) != 1:
        named = makes | {make for make, _ in models}
        return (named.pop() if len(named) == 1 else None), None, None, None, None
    (make, model), = models
    years = sorted(int(y) for y in re.findall(YEAR, text))
    year_from, year_to = (years[0], years[-1]) if years else (None, None)
    key = f"{make}-{model}" + (f"-{year_from}-{year_to}" if years else "")
    return make, model, year_from, year_to, key


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
