import re
from typing import Optional, Tuple, Dict
from .normalize import slugify


LOWER_WORDS_ES = {"de","del","la","las","los","y","e","en","con","sin","al","a","por","para"}

# IMPORTANTE: usar | (no saltos de línea)
CAT_WORDS_RE = re.compile(r"\b(infantil|cadete|juvenil|junior|júnior|absoluto|absoluta|master|máster)\b", re.IGNORECASE)
SEX_WORDS_RE = re.compile(r"\b(masculino|masculina|femenino|femenina|mixto|mixta)\b", re.IGNORECASE)
MEN_EN_RE = re.compile(r"\bmen(?:'s)?\b", re.IGNORECASE)
WOMEN_EN_RE = re.compile(r"\bwomen(?:'s)?\b", re.IGNORECASE)

# Máster con acento o sin acento
MASTER_WORD = r"ma[áa]ster"

# Máster rango: "Máster 30-34" / "Máster +70"
MASTER_RANGE_RE = re.compile(
    rf"\b{MASTER_WORD}\s*(?P<range>\d{{2}}\s*-\s*\d{{2}}|\+\s*\d{{2}})\b",
    re.IGNORECASE
)

# Máster R4 (relevos): "MásterR4 +170" / "Máster R4 +170"
MASTER_R4_RE = re.compile(
    rf"\b{MASTER_WORD}\s*r4\s*(?P<sum>\+\s*\d{{2,3}})\b",
    re.IGNORECASE
)

# Variante pegada "MásterR4" (sin espacio)
MASTER_R4_GLUE_RE = re.compile(
    rf"\b{MASTER_WORD}r4\s*(?P<sum>\+\s*\d{{2,3}})\b",
    re.IGNORECASE
)

MASTER_BLOCK_RE = re.compile(
    r"\bma[áa]ster(?:\s*r4|r4)?\s*(?:\+\s*\d{2,3}|\d{2}\s*-\s*\d{2}|\+\s*\d{2})\b",
    re.IGNORECASE
)

# Detecta distancia en cualquier parte:
# - 4x12,5 m. / 4x12.5m / 4x50m.
# - 200m / 200 m / 200m.
DIST_ANY_RE = re.compile(
    r"(?P<relay>4x)\s*(?P<num>\d+(?:[.,]\d+)?)\s*m\.?|(?P<num2>\d{2,3})\s*m\.?",
    re.IGNORECASE
)

CATEGORY_LINE_RE = re.compile(r"^\s*(.+?)\s*\((.+?)\)\s*$", re.IGNORECASE)


def title_case_es(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip())
    out = []
    for i, w in enumerate(s.split()):
        wl = w.lower()
        if i > 0 and wl in LOWER_WORDS_ES:
            out.append(wl)
        else:
            out.append(wl[:1].upper() + wl[1:])
    return " ".join(out)


def strip_category_sex_es(s: str) -> str:
    s = re.sub(r"\bcategor[ií]a\b", "", s or "", flags=re.IGNORECASE)

    # Quitar bloque completo Máster (rango o R4 +xxx)
    s = MASTER_BLOCK_RE.sub("", s)

    # Quitar palabras de categorías estándar (incluye cadete/infantil/master/máster)
    s = CAT_WORDS_RE.sub("", s or "")
    s = SEX_WORDS_RE.sub("", s)
    return re.sub(r"\s+", " ", s).strip()


def is_line_throw(text: str) -> bool:
    t = (text or "").lower()
    return ("line throw" in t) or ("lanzamiento de cuerda" in t)


def infer_relay(text: str) -> bool:
    t = (text or "").lower()
    return ("4x" in t) or is_line_throw(t) or ("relevo" in t)


def sex_code(raw: Optional[str]) -> str:
    r = (raw or "").lower()

    # Español (tolerante a OCR/typos: femenenina, femenina, etc.)
    if re.search(r"\bfemen\w*", r):
        return "F"
    if re.search(r"\bmascul\w*", r):
        return "M"
    if re.search(r"\bmixt\w*", r):
        return "X"

    # Inglés (solo como palabra: evita "femenino" -> "men")
    if WOMEN_EN_RE.search(r):
        return "F"
    if MEN_EN_RE.search(r):
        return "M"

    return "X"


def category_code(raw: Optional[str]) -> str:
    r = (raw or "").lower()

    if "cadete" in r:
        return "cadete"
    if "infantil" in r:
        return "infantil"

    # Máster R4 +xxx (con o sin espacio)
    m = MASTER_R4_RE.search(r) or MASTER_R4_GLUE_RE.search(r)
    if m:
        val = re.sub(r"\s+", "", m.group("sum"))  # "+170"
        return f"master_r4_{val}"

    # Máster rango 30-34 / +70
    m = MASTER_RANGE_RE.search(r)
    if m:
        val = re.sub(r"\s+", "", m.group("range"))  # "45-49" o "+70"
        return f"master_{val}"

    if "juvenil" in r:
        return "juvenil"
    if "junior" in r or "júnior" in r or "nior" in r:
        return "junior"
    if "absolut" in r:
        return "absoluto"
    return "absoluto"


def category_display(cat: str) -> str:
    if cat == "cadete":
        return "Cadete"
    if cat == "infantil":
        return "Infantil"
    if cat.startswith("master_r4_"):
        return "Máster R4 " + cat.split("master_r4_", 1)[1].replace("_", "")
    if cat.startswith("master_"):
        return "Máster " + cat.split("master_", 1)[1].replace("_", "")
    if cat == "juvenil":
        return "Juvenil"
    if cat == "junior":
        return "Junior"
    return "Absoluto"


def _normalize_distance_prefix(relay: bool, num_str: str) -> Tuple[str, str]:
    """
    Devuelve:
      - prefix_text: "200 m." / "4x12,5 m."
      - distance_text: "200" / "4x12,5"
    """
    num = float(num_str.replace(",", "."))
    # display sin .0 y con coma decimal
    num_disp = str(int(num)) if num.is_integer() else str(num).replace(".", ",")
    prefix_text = f"{'4x' if relay else ''}{num_disp} m."
    distance_text = f"{'4x' if relay else ''}{num_disp}"
    return prefix_text, distance_text


def extract_distance_from_title(event_title: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Busca distancia en cualquier parte del título (EN o ES):
      - 200m / 200 m / 200m.
      - 4x50m / 4x12,5m / 4x12.5 m.
    Devuelve (prefix_text, distance_m).
    """
    s = event_title or ""
    m = DIST_ANY_RE.search(s)
    if not m:
        return None, None

    if m.group("relay") and m.group("num"):
        return _normalize_distance_prefix(True, m.group("num"))

    if m.group("num2"):
        return _normalize_distance_prefix(False, m.group("num2"))

    return None, None


def build_event_fields(event_title: str, category_line: Optional[str]) -> Dict:
    """
    Construye:
      base (capitalized, sin cat/sex), distance_m, relay, category, sex (F/M/X), id
    """
    # >>> DEBUG TEMPORAL (borra después) <<<
    debug_info_1 = None
    if "máster" in event_title.lower() or "master" in event_title.lower():
        debug_info_1 = {
            "event_title": event_title,
        }
    # >>> FIN DEBUG TEMPORAL <<<
    raw_title = event_title or ""

    # tramo ES tras el guion si existe
    es_part = raw_title
    if re.search(r"\s-\s", raw_title):
        es_part = re.split(r"\s-\s", raw_title, maxsplit=1)[1].strip()

    # category/sex preferidos desde category_line
    cat = None
    sex_source = " ".join([raw_title, es_part, category_line or ""])
    sx = sex_code(sex_source)
    if category_line:
        m = CATEGORY_LINE_RE.match(category_line)
        if m:
            cat_candidate = category_code(m.group(1)) or cat
            sx_candidate = sex_code(m.group(2))
            if sx_candidate != "X":  # si detecta sexo válido en category_line, lo usamos (sobrescribe sex)
                sx = sx_candidate

            # Validación: si el texto NO contiene categoría real, no lo uses
            if re.search(r"\b(infantil|cadete|juvenil|junior|júnior|absolut|m[aá]ster)\b", m.group(1), re.IGNORECASE):
                cat = cat_candidate
            # Validación: si el texto NO contiene sexo real, no lo uses
            if re.search(r"\b(femen\w*|mascul\w*|mixt\w*|women|men)\b", m.group(2), re.IGNORECASE):
                sx = sx_candidate

    # fallback desde event_title si no vienen en category_line
    if not sx:
        sx = sex_code(raw_title)

    debug_info_2 = None
    if not cat:
        cat = category_code(raw_title)
        # >>> DEBUG TEMPORAL (borra después) <<<
        debug_info_2 = {
            "category code": cat,
        }
        # >>> FIN DEBUG TEMPORAL <<<



    relay = infer_relay(raw_title + " " + es_part)

    # Lanzamiento de cuerda: relevo sin distancia
    if is_line_throw(es_part) or is_line_throw(raw_title):
        base = "Lanzamiento de Cuerda"
        distance_m = None
    else:
        # extraer distancia en cualquier parte del título (EN o ES)
        prefix, distance_m = extract_distance_from_title(raw_title)
        # limpiar texto ES: quitar cat/sex y title case
        rest = strip_category_sex_es(es_part)
        rest = title_case_es(rest)
        # Si el texto ES ya trae distancia al inicio ("50 m.", "4x25 m.", "4x12,5 m."),
        # la quitamos para no duplicarla al anteponer prefix.
        rest = re.sub(r"^(?:4x)?\s*\d+(?:[.,]\d+)?\s*m\.?\s*", "", rest, flags=re.IGNORECASE).strip()

        if prefix:
            base = f"{prefix} {rest}".strip()
        else:
            # si no hay distancia detectada, dejamos solo el texto (caso raro)
            base = rest.strip()

    sex = sx  # F/M/X
    category = cat # juvenil/junior/absoluto
    event_id = "e_" + slugify(f"{base}_{category}_{sex}").lower()

    # >>> DEBUG TEMPORAL (borra después) <<<
    debug_info = None
    if "máster" in raw_title.lower() or "master" in raw_title.lower():
        debug_info = {
            "raw_title": raw_title,
            "es_part": es_part,
            "category_line": category_line,
            "cat": cat,
            "sex": sx,
            "base": base,
            "distance_m": distance_m,
            "relay": relay,
            "id": event_id,
        }
    # >>> FIN DEBUG TEMPORAL <<<

    return {
        "base": base,
        "distance_m": distance_m,
        "relay": relay,
        "category": category,
        "category_display": category_display(category),
        "sex": sex,
        "id": event_id,
        "debug_info_1": debug_info_1,
        "debug_info_2": debug_info_2,
        "debug_info": debug_info,
    }