import re
from typing import Optional, Tuple, Dict
from .normalize import slugify

LOWER_WORDS_ES = {"de","del","la","las","los","y","e","en","con","sin","al","a","por","para"}

# ✅ IMPORTANTE: usar | (no saltos de línea)
CAT_WORDS_RE = re.compile(r"\b(juvenil|junior|júnior|absoluto|absoluta)\b", re.IGNORECASE)
SEX_WORDS_RE = re.compile(r"\b(masculino|masculina|femenino|femenina|mixto|mixta)\b", re.IGNORECASE)

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
    # Inglés
    if "women" in r:
        return "F"
    if "men" in r:
        return "M"
    # Español (clave para tus PDFs)
    if "femenin" in r:   # femenino/femenina
        return "F"
    if "masculin" in r:  # masculino/masculina
        return "M"
    # Mixto
    if "mixt" in r:
        return "X"
    # fallback
    return "X"


def category_code(raw: Optional[str]) -> str:
    r = (raw or "").lower()
    if "juvenil" in r:
        return "juvenil"
    if "junior" in r or "júnior" in r or "nior" in r:
        return "junior"
    if "absolut" in r:
        return "absoluto"
    return "absoluto"  # default si no se detecta


def _normalize_distance_prefix(relay: bool, num_str: str) -> Tuple[str, float]:
    num = float(num_str.replace(",", "."))
    dist_val = int(num) if num.is_integer() else num
    num_disp = str(int(num)) if float(num).is_integer() else str(num).replace(".", ",")
    prefix = f"{'4x' if relay else ''}{num_disp} m."
    return prefix, float(dist_val)

def extract_distance_from_title(event_title: str) -> Tuple[Optional[str], Optional[float]]:
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
    raw_title = event_title or ""

    # tramo ES tras el guion si existe
    es_part = raw_title
    if "-" in raw_title:
        es_part = raw_title.split("-", 1)[1].strip()

    # category/sex preferidos desde category_line
    cat = None
    sex_source = " ".join([raw_title, es_part, category_line or ""])
    sx = sex_code(sex_source)
    if category_line:
        m = CATEGORY_LINE_RE.match(category_line)
        if m:
            cat_candidate = category_code(m.group(1))
            sx_candidate = sex_code(m.group(2))

            # Validación: si el texto NO contiene categoría real, no lo uses
            if re.search(r"\b(juvenil|junior|júnior|absolut)\b", m.group(1), re.IGNORECASE):
                cat = cat_candidate
            # Validación: si el texto NO contiene sexo real, no lo uses
            if re.search(r"\b(femenin|masculin|mixt|women|men)\b", m.group(2), re.IGNORECASE):
                sx = sx_candidate

    # fallback desde event_title si no vienen en category_line
    if not sx:
        sx = sex_code(raw_title)
    if not cat:
        cat = category_code(raw_title)

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

        if prefix:
            base = f"{prefix} {rest}".strip()
        else:
            # si no hay distancia detectada, dejamos solo el texto (caso raro)
            base = rest.strip()

    sex = sx  # F/M/X
    category = cat # juvenil/junior/absoluto
    event_id = "e_" + slugify(f"{base}_{category}_{sex}").lower()

    return {
        "base": base,
        "distance_m": distance_m,
        "relay": relay,
        "category": category,
        "sex": sex,
        "id": event_id,
    }