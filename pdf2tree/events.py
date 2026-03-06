import re
from typing import Optional, Tuple
from .normalize import slugify


LOWER_WORDS_ES = {"de","del","la","las","los","y","e","en","con","sin","al","a","por","para"}

# quita categoría y sexo (ES) del texto de disciplina
CAT_WORDS_RE = re.compile(r"\b(juvenil|junior|júnior|absoluto|absoluta)\b", re.IGNORECASE)
SEX_WORDS_RE = re.compile(r"\b(masculino|masculina|femenino|femenina|mixto|mixta)\b", re.IGNORECASE)

DIST_PREFIX_RE = re.compile(
    r"^(?P<relay>4x)?\s*(?P<num>\d+(?:[.,]\d+)?)\s*m\.?\s*(?P<rest>.*)$",
    re.IGNORECASE
)

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
    s = CAT_WORDS_RE.sub("", s or "")
    s = SEX_WORDS_RE.sub("", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_distance_prefix(s: str) -> Tuple[Optional[str], Optional[float], str]:
    """
    Devuelve:
      - prefix_text: "50 m." o "4x12,5 m." o None
      - distance_m: 50 / 12.5 / 200 (float o int) o None
      - rest: texto restante tras el prefijo
    Soporta: 200m, 200 m., 4x12.5m, 4x12,5 m., etc.
    """
    s = (s or "").strip()
    m = DIST_PREFIX_RE.match(s)
    if not m:
        return None, None, s

    relay = bool(m.group("relay"))
    num_raw = m.group("num").replace(",", ".")
    num = float(num_raw)
    distance_m = int(num) if num.is_integer() else num

    # para display: decimal con coma
    num_disp = str(int(num)) if float(num).is_integer() else str(num).replace(".", ",")
    prefix_text = f"{'4x' if relay else ''}{num_disp} m."
    rest = (m.group("rest") or "").strip()
    return prefix_text, distance_m, rest


def is_line_throw(text: str) -> bool:
    t = (text or "").lower()
    return ("line throw" in t) or ("lanzamiento de cuerda" in t)


def infer_relay(text: str) -> bool:
    t = (text or "").lower()
    return ("4x" in t) or is_line_throw(t) or ("relevo" in t)


def sex_code(raw: Optional[str]) -> str:
    r = (raw or "").lower()
    if "women" in r or "fem" in r:
        return "F"
    if "men" in r or "masc" in r:
        return "M"
    if "mixt" in r:
        return "X"
    return "X"  # default seguro (mejor X que None)


def category_code(raw: Optional[str]) -> str:
    r = (raw or "").lower()
    if "juvenil" in r:
        return "juvenil"
    if "junior" in r or "júnior" in r or "nior" in r:
        return "junior"
    if "absolut" in r:
        return "absoluto"
    return "absoluto"


def build_event_fields(event_title: str, category_line: Optional[str]) -> dict:
    """
    event_title: línea tipo "Women's 4x50m. ... - relevo ... juvenil femenino"
    category_line: opcional "juvenil (femenina)" / "júnior (masculina)" etc.

    Devuelve dict con:
      base, distance_m, relay, category, sex, id
    """
    raw_title = event_title or ""
    # cogemos preferentemente el tramo ES tras el guion (si existe)
    es_part = raw_title
    if "-" in raw_title:
        es_part = raw_title.split("-", 1)[1].strip()

    # category/sex: preferimos category_line si existe
    cat = None
    sx = None
    if category_line:
        m = re.match(r"^\s*(.+?)\s*\((.+?)\)\s*$", category_line, re.IGNORECASE)
        if m:
            cat = category_code(m.group(1))
            sx = sex_code(m.group(2))

    if not sx:
        sx = sex_code(raw_title)
    if not cat:
        cat = category_code(raw_title)

    # relay?
    relay = infer_relay(raw_title + " " + es_part)

    # Lanzamiento de cuerda: sin distancia
    if is_line_throw(es_part) or is_line_throw(raw_title):
        base_core = "Lanzamiento de Cuerda"
        distance_m = None
        base = base_core
    else:
        # extraer prefijo de distancia (puede venir pegado 200m / 4x50m.)
        prefix, distance_m, rest = parse_distance_prefix(es_part)
        rest = strip_category_sex_es(rest)
        rest = title_case_es(rest)

        # si no venía prefijo pero el evento_title tenía distancia EN (p.ej. "200m.") y el ES no,
        # parse_distance_prefix no lo verá. En ese caso intentar sobre el title completo:
        if not prefix:
            prefix2, distance_m2, rest2 = parse_distance_prefix(raw_title)
            if prefix2:
                prefix, distance_m = prefix2, distance_m2

        if prefix:
            base = f"{prefix} {rest}".strip()
        else:
            base = rest.strip()

    # base ya viene sin categoría/sexo; category y sex van aparte
    sex = sx
    category = cat

    event_id = "e_" + slugify(f"{base}_{category}_{sex}").lower()

    return {
        "base": base,
        "distance_m": distance_m,
        "relay": relay,
        "category": category,
        "sex": sex,
        "id": event_id,
    }