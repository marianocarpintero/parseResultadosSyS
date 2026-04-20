# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Mariano Carpintero
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.


import re
from typing import Optional, Tuple, Dict
from .normalize import normalize_key, slugify, strip_accents, normalize_spaces, normalize_dashes


LOWER_WORDS_ES = {"de","del","la","las","los","y","e","en","con","sin","al","a","por","para"}

CAT_WORDS_RE = re.compile(
    r"\b(infantil|inf\.?|cadete|cad\.?|juvenil|juv\.?|junior|júnior|jun\.?|absoluto|absoluta|abs\.?|master|máster)\b",
    re.IGNORECASE
)

JUV_JUN_RE = re.compile(r"\bjuvenil\b\s*-\s*\bjun(?:ior|i[oó]r)\b", re.IGNORECASE)

_CAT_ABBR_FIXES = [
    (re.compile(r"\bjuv\s+jun\b", re.IGNORECASE), "Juvenil - Júnior"),
    (re.compile(r"\bjuv\b", re.IGNORECASE), "Juvenil"),
    (re.compile(r"\bjun\b", re.IGNORECASE), "Júnior"),
    (re.compile(r"\babs\b", re.IGNORECASE), "Absoluto"),
    (re.compile(r"\bcad\b", re.IGNORECASE), "Cadete"),
    (re.compile(r"\binf\b", re.IGNORECASE), "Infantil"),
]

SEX_WORDS_RE = re.compile(r"\b(masculino|masculina|femenino|femenina|mixto|mixta)\b", re.IGNORECASE)

# sexo abreviado
_SEX_ABBR_FIXES = [
    (re.compile(r"\bmas\b", re.IGNORECASE), "Masculino"),
    (re.compile(r"\bfem\b", re.IGNORECASE), "Femenino"),
    (re.compile(r"\bmix\b", re.IGNORECASE), "Mixto"),
]

_GLUE_SEX_TO_WORD_RE = re.compile(r"(\b[MFxX]\b)(?=[A-Za-zÁÉÍÓÚÑáéíóúñ])")

_GLUE_RANGE_SEX_RE = re.compile(r"(\d{2}\s*-\s*\d{2})([MFxX])\b")

_TRAILING_SEX_LETTER_RE = re.compile(r"\b([MFxX])\b\s*$")

_INLINE_SEX_BEFORE_CAT_RE = re.compile(
    r"\b([MFxX])\b(?=\s+(?:agrupad[oa]|absolut\w*|junior|júnior|juvenil|master|m[áa]ster)\b)",
    re.IGNORECASE
)

MEN_EN_RE = re.compile(r"\bmen(?:'s)?\b", re.IGNORECASE)

WOMEN_EN_RE = re.compile(r"\bwomen(?:'s)?\b", re.IGNORECASE)

# Máster con acento o sin acento
MASTER_WORD = re.compile(r"m[áa]ster", re.IGNORECASE).pattern

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
    r"\bm[áa]ster(?:\s*r4|r4)?\s*(?:\+\s*\d{2,3}|\d{2}\s*-\s*\d{2}|\+\s*\d{2})\b",
    re.IGNORECASE
)

MASTER_WORD_RE = re.compile(r"\bm[áa]ster\b", re.IGNORECASE)

_MASTER_PLUS_3_RE = re.compile(r"^master_\+\d{3}$")

_TRAILING_MASTER_RE = re.compile(r"\bm[áa]ster\b\s*$", re.IGNORECASE)

_DUPLICATE_TRAILING_MASTER_RE = re.compile(
    r"(m[áa]ster\s+r\d+\s*\+\s*\d{3})\s+m[áa]ster\b",
    re.IGNORECASE
)

SEX_TAIL_RE = re.compile(r"\b(femen\w*|mascul\w*|mixt\w*)\b", re.IGNORECASE)

# Detecta distancia en cualquier parte (EN o ES), tolerante:
# - "200m", "200 m", "200 m.", "200" (sin m)  [ya lo separa normalize_event_title_variants]
# - "4x50m", "4x50 m", "4 x 50 m", "4x12,5m", "4x12.5 m"
DIST_ANY_RE = re.compile(
    r"(?P<relay>4\s*x)\s*(?P<num>\d+(?:[.,]\d+)?)\s*(?:\u202F|\s)?m\.?\b"
    r"|(?P<num2>\d{2,3})\s*(?:\u202F|\s)?m\.?\b",
    re.IGNORECASE
)

CATEGORY_LINE_RE = re.compile(r"^\s*(.+?)\s*\((.+?)\)\s*$", re.IGNORECASE)

EVENT_NAME_ES = {
    "line throw": "Lanzamiento de Cuerda",
    "obstacle swim": "Natación con Obstáculos",
    "obstacle relay": "Relevo Natación con Obstáculos",
    "manikin carry": "Remolque de Maniquí",
    "manikin relay": "Relevo Remolque de Maniquí",
    "medley relay": "Relevo Combinado",
    "super lifesaver": "Supersocorrista",
    "manikin tow with fins": "Socorrista",
    "manikin carry with fins": "Remolque de Maniquí con Aletas",
    "manikin carry with rubber fins": "Remolque de Maniquí con Aletas de Goma",
    "rescue medley": "Combinada de Salvamento",
    "pool lifesaver relay": "Relevo Socorrista"
}

DEFAULT_EVENT_DISTANCE_M = {
    "natación con obstáculos": "200",
    "obstacle swim": "200",
    "relevo natación con obstáculos": "4x50",
    "obstacle relay": "4x50",

    "socorrista": "100",
    "manikin tow with fins": "100",
    "relevo socorrista": "4x50",
    "pool lifesaver relay": "4x50",

    "remolque de maniquí": "50",
    "manikin carry": "50",
    "relevo remolque de maniquí": "4x25",
    "relevo arrastre de maniquí": "4x25",
    "manikin relay": "4x25",

    "remolque de maniquí con aletas": "100",
    "manikin carry with fins": "100",
    "remolque de maniquí con aletas de goma": "100",
    "manikin carry with rubber fins": "100",

    "combinada de salvamento": "100",
    "rescue medley": "100",

    "supersocorrista": "200",
    "super lifesaver": "200",

    "relevo combinado": "4x50",
    "medley relay": "4x50",
    # Añade aquí más disciplinas según tus necesidades
}


# distancia pegada tipo 100m / 4x50m
_DISTANCE_GLUE_RE = re.compile(r"\b(\d{2,3}|4\s*x\s*\d+(?:[.,]\d+)?)m\b", re.IGNORECASE)

_DUP_WORDS_RE = re.compile(r"\b(\w+)\b(?:\s+\1\b)+", re.IGNORECASE)


def collapse_duplicate_words(text: str) -> str:
    """
    Colapsa repeticiones consecutivas de la misma palabra:
      - 'Máster Máster 30-39' -> 'Máster 30-39'
      - 'juvenil juvenil (Femenino)' -> 'juvenil (Femenino)'
    No toca repeticiones no consecutivas.
    """
    if not text:
        return text
    prev = None
    cur = normalize_spaces(text)
    # iterar hasta estabilizar (por si hay 3 repeticiones)
    while prev != cur:
        prev = cur
        cur = _DUP_WORDS_RE.sub(r"\1", cur)
        cur = normalize_spaces(cur)
    return cur


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

    # Quitar sufijos sueltos de sexo en letra: " M", " F", " X" (típico en títulos "Master M/F")
    s = re.sub(r"\s+\b([mfx])\b\s*$", "", s, flags=re.IGNORECASE)
    
    return re.sub(r"\s+", " ", s).strip()


def is_line_throw(text: str) -> bool:
    t = (text or "").lower()
    return (
        ("line throw" in t)
        or ("lanzamiento de cuerda" in t)
        or ("lanzamiento cuerda" in t)
    )

def infer_relay(text: str) -> bool:
    t = (text or "").lower()
    return (
        ("4x" in t)
        or is_line_throw(t)
        or ("relevo" in t)
        or bool(re.search(r"\brelay\b", t))
    )


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


def _fix_glued_sex_letter(text: str) -> str:
    """
    Arregla casos típicos de extract_text: '... FSeries ...' -> '... F Series ...'
    Solo actúa cuando hay una letra de sexo seguida inmediatamente de letra.
    """
    if not text:
        return text
    return _GLUE_SEX_TO_WORD_RE.sub(r"\1 ", text)


def translate_event_name_es(base: str) -> str:
    if not base:
        return base
    return EVENT_NAME_ES.get(base.lower(), base)


def _fix_glued_tokens(text: str) -> str:
    """Normaliza pegados típicos del OCR/extract_text."""
    if not text:
        return text
    text = _GLUE_SEX_TO_WORD_RE.sub(r"\1 ", text)
    text = _GLUE_RANGE_SEX_RE.sub(r"\1 \2", text)
    return text


def _extract_trailing_sex_letter(text: str) -> tuple[str | None, str]:
    """
    Si el texto termina en ' ... F' / ' ... M' / ' ... X', devuelve (sexo, texto_sin_letra).
    """
    if not text:
        return None, text
    m = _TRAILING_SEX_LETTER_RE.search(text.strip())
    if not m:
        return None, text
    sex = m.group(1).upper()
    # quitar el último token (la letra)
    stripped = _TRAILING_SEX_LETTER_RE.sub("", text).strip()
    return sex, stripped


def _extract_inline_sex_letter(text: str) -> tuple[Optional[str], str]:
    """
    Detecta sexo como letra suelta antes de la categoría:
    'Obstacle Swim F Agrupada' -> ('F', 'Obstacle Swim Agrupada')
    """
    if not text:
        return None, text
    m = _INLINE_SEX_BEFORE_CAT_RE.search(text)
    if not m:
        return None, text
    sex = m.group(1).upper()
    # quita SOLO esa letra (una ocurrencia) y normaliza espacios
    stripped = _INLINE_SEX_BEFORE_CAT_RE.sub("", text, count=1)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    return sex, stripped


def category_code(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    r = (raw or "").lower()

    # Combinado Juvenil - Júnior
    if JUV_JUN_RE.search(raw):
        return "juvenil_junior"
    # también si aparecen ambas palabras aunque no haya guion exacto
    if ("juvenil" in r) and ("junior" in r or "júnior" in r or "nior" in r):
        return "juvenil_junior"

    # Palabras completas
    if re.search(r"\bcadete\b", r):
        return "cadete"
    if re.search(r"\binfantil\b", r):
        return "infantil"
    if re.search(r"\bjuvenil\b", r):
        return "juvenil"
    if re.search(r"\bjunior\b", r) or re.search(r"\bjúnior\b", r):
        return "junior"
    if re.search(r"\babsolut[oa]?\b", r):
        return "absoluto"

  # Abreviaturas
    if re.search(r"\bcad\.?\b", r):
        return "cadete"
    if re.search(r"\binf\.?\b", r):
        return "infantil"
    if re.search(r"\bjuv\.?\b", r):
        return "juvenil"
    if re.search(r"\bjun\.?\b", r):
        return "junior"
    if re.search(r"\babs\.?\b", r):
        return "absoluto"

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
    
    return "absoluto"


def category_display(cat: str) -> str:
    """
    Devuelve la representación textual de la categoría:
    - SIEMPRE en femenino (concuerda con el campo 'categoría')
    - 'Máster' siempre capitalizado y con tilde
    """
    if not cat:
        return "Absoluta"

    c = cat.strip().lower()
    if c == "juvenil_junior":
        return "Juvenil - Júnior"

    # Categorías invariables en género
    if cat in {"infantil", "juvenil"}:
        return cat.capitalize()
    if cat == "junior":
        return "Júnior"

    # Cadete -> Cadete (invariable en uso deportivo)
    if cat == "cadete":
        return "Cadete"

    # Absoluto -> Absoluta
    if cat == "absoluto":
        return "Absoluta"

    # Combinado -> Combinada (si lo tienes en algún PDF)
    if cat == "combinado":
        return "Combinada"

    # Máster R4 (+xxx)
    if cat.startswith("master_r4_"):
        val = cat.split("master_r4_", 1)[1].replace("_", "")
        return _normalize_master_display(f"Máster R4 {val}")

    # Máster rangos / sumas
    if cat.startswith("master_"):
        val = cat.split("master_", 1)[1].replace("_", "")
        return _normalize_master_display(f"Máster {val}")

    # Fallback defensivo
    return "Absoluta"


def _normalize_master_display(s: str) -> str:
    """
    Fuerza 'Máster' con tilde y mayúscula, y normaliza 'R4' si aplica.
    """
    if not s:
        return s
    t = re.sub(r"\s+", " ", s).strip()
    # 'master' / 'máster' / 'Master' -> 'Máster'
    t = re.sub(r"\bm[áa]ster\b", "Máster", t, flags=re.IGNORECASE)
    # Normaliza R4 (si viene raro)
    t = re.sub(r"\bR\s*4\b", "R4", t, flags=re.IGNORECASE)
    return t


def _normalize_category_display_es(s: Optional[str]) -> str:
    if not s:
        return ""
    t = normalize_spaces(s)

    # Fuerza Máster (tilde + mayúscula)
    t = re.sub(r"\bm[áa]ster\b", "Máster", t, flags=re.IGNORECASE)

    # (Opcional) Refuerza Júnior si te interesa blindarlo también
    t = re.sub(r"\bJunior\b", "Júnior", t)

    return t


def extract_master_category_and_trim(title: str) -> tuple[Optional[str], str]:
    """
    Si encuentra 'máster/master' devuelve:
      - category_display: p.ej. 'Máster 30-34' / 'Máster R4 +170'
      - trimmed_title: título SIN la parte de máster en adelante (para construir base)
    Si no encuentra máster: (None, title)
    """
    if not title:
        return None, title

    m = MASTER_WORD_RE.search(title)
    
    if not m:
        return None, title

    # segmento desde 'máster' hasta final
    seg = title[m.start():].strip()

    # quitar sexo dentro del segmento
    seg = SEX_TAIL_RE.sub("", seg).strip()
    seg = re.sub(r"\s+", " ", seg)

    # normalizar MásterR4 / Máster R4
    seg = re.sub(r"\bm[áa]ster\s*r4\b", "Máster R4", seg, flags=re.IGNORECASE)
    seg = re.sub(r"\bm[áa]sterr4\b", "Máster R4", seg, flags=re.IGNORECASE)

    # asegurar "Máster" con acento al inicio
    seg = re.sub(r"^m[áa]ster", "Máster", seg, flags=re.IGNORECASE)

    # Si el segmento es solo "Máster/Master M|F|X" (sin rango), NO lo tratamos como categoría máster
    if re.fullmatch(r"(?:Máster|master)(?:\s+[MFX])?", seg, flags=re.IGNORECASE):
        return None, title    

    # trimmed_title: todo lo anterior a 'máster'
    trimmed = (title[:m.start()]).strip()
    trimmed = re.sub(r"\s+", " ", trimmed)

    return seg, trimmed


def master_category_to_canonical(cat_display: str) -> str:
    """
    Convierte display 'Máster 30-34' / 'Máster R4 +170' a canónica:
      - master_30-34
      - master_r4_+170
      - master_+70
    """
    s = (cat_display or "").strip()
    s = s.replace("Máster", "master").replace("máster", "master")
    s = s.replace("R4", "r4")
    s = re.sub(r"\s+", " ", s)

    # "master r4 +170" -> master_r4_+170
    if s.lower().startswith("master r4"):
        rest = s[9:].strip()  # quita "master r4"
        rest = re.sub(r"\s+", "", rest)  # "+170"
        return f"master_r4_{rest}"

    # "master 30-34" o "master +70"
    rest = s[6:].strip()  # quita "master"
    rest = re.sub(r"\s+", "", rest)      # "30-34" / "+70"
    return f"master_{rest}" if rest else "master"


def _is_multi_master_display(master_display: Optional[str]) -> bool:
    """
    Devuelve True si el segmento 'Máster ...' contiene MÁS de un rango/suma.
    Ejemplos:
    - "Máster 60-64 y 70-74" -> True
    - "Máster +120 y +140"  -> True
    """
    if not master_display:
        return False

    s = master_display.lower()

    # cuenta rangos tipo 60-64
    ranges = re.findall(r"\b\d{2}\s*-\s*\d{2}\b", s)
    # cuenta sumas tipo +120 / +140 / +200
    sums = re.findall(r"\+\s*\d{2,3}\b", s)

    has_two_ranges = len(ranges) >= 2
    has_two_sums = len(sums) >= 2
    has_y_with_any = (" y " in s) and ((len(ranges) > 0) or (len(sums) > 0))

    return has_two_ranges or has_two_sums or has_y_with_any


def _force_r4_for_master_plus_3(cat: Optional[str], relay: bool) -> Optional[str]:
    """
    Si es relevo y la categoría canónica es 'master_+XYZ' (XYZ = 3 cifras),
    forzar 'master_r4_+XYZ'.
    """
    if not relay or not cat:
        return cat
    if _MASTER_PLUS_3_RE.match(cat) and not cat.startswith("master_r4_"):
        return "master_r4_" + cat.split("master_", 1)[1]
    return cat


def _strip_trailing_master(s: str) -> str:
    """Elimina un 'Máster' sobrante al final: 'Máster R4 +170 Máster' -> 'Máster R4 +170'."""
    if not s:
        return s
    t = normalize_spaces(s)
    t = _TRAILING_MASTER_RE.sub("", t).strip()
    return normalize_spaces(t)


def _normalize_distance_prefix(relay: bool, num_str: str) -> Tuple[str, str]:
    """
    Devuelve:
      - prefix_text: "200 m" / "4x12,5 m"
      - distance_text: "200" / "4x12,5"
    """
    num = float(num_str.replace(",", "."))
    # display sin .0 y con coma decimal
    num_disp = str(int(num)) if num.is_integer() else str(num).replace(".", ",")

    # Formato ES correcto: número + espacio corto (U+202F) + "m" sin punto + espacio normal
    prefix_text = f"{'4x' if relay else ''}{num_disp}\u202Fm"

    distance_text = f"{'4x' if relay else ''}{num_disp}"

    return prefix_text, distance_text


def extract_distance_from_title(event_title: str) -> Tuple[Optional[str], Optional[str]]:
    s = event_title or ""
    m = DIST_ANY_RE.search(s)
    if not m:
        return None, None

    if m.group("relay") and m.group("num"):
        return _normalize_distance_prefix(True, m.group("num"))

    if m.group("num2"):
        return _normalize_distance_prefix(False, m.group("num2"))

    return None, None


def canonicalize_event_key(text: str) -> str:
    """
    Lleva entradas EN/ES (y variantes típicas) a una clave canónica EN
    para:
      - traducir de forma estable (EVENT_NAME_ES)
      - asignar distancia por defecto (DEFAULT_EVENT_DISTANCE_M)
    """
    t = normalize_spaces(strip_accents(text or "")).lower()

    # Normalizaciones comunes (quita dobles espacios, etc.)
    t = re.sub(r"\s+", " ", t).strip()

    # EN -> canonical
    if "obstacle swim" in t:
        return "obstacle swim"
    if "obstacle relay" in t:
        return "obstacle relay"
    if "manikin tow with fins" in t:
        return "manikin tow with fins"
    if "manikin carry with fins" in t:
        return "manikin carry with fins"
    if "manikin carry" in t:
        return "manikin carry"
    if "manikin relay" in t:
        return "manikin relay"
    if "line throw" in t:
        return "line throw"
    if "super lifesaver" in t:
        return "super lifesaver"
    if "rescue medley" in t:
        return "rescue medley"
    if "medley relay" in t:
        return "medley relay"
    if "pool lifesaver relay" in t:
        return "pool lifesaver relay"

    # ES -> canonical (sin tildes ya)
    if "natacion con obstaculos" in t:
        return "obstacle swim"
    if "remolque" in t and "aletas" in t and "infantil" in t:
        # Caso especial: Remolque Aletas Inf => Aletas de Goma
        return "manikin carry with rubber fins"
    if "remolque" in t and "aletas" in t:
        return "manikin carry with fins"  
    if "arrastre de maniqui con aletas" in t:
        return "manikin tow with fins"
    if t == "arrastre de maniqui con aletas" or "remolque de maniqui con aletas" in t:
        return "manikin carry with fins"
    if t == "arrastre de maniqui" or "remolque de maniqui" in t:
        return "manikin carry"
    if "remolque" in t:
        return "manikin carry"
    if "supersocorrista" in t:
        return "super lifesaver"
    if "socorrista" in t:
        return "manikin tow with fins"
    if t == "relevo arrastre de maniqui" or "relevo remolque de maniqui" in t:
        return "manikin relay"
    if "lanzamiento" in t and "cuerda" in t:
        return "line throw"
    if "relevo natacion con obstaculos" in t:
        return "obstacle relay"
    if "combinada de salvamento" in t:
        return "rescue medley"
    if "relevo combinado" in t:
        return "medley relay"
    if "relevo socorrista" in t:
        return "pool lifesaver relay"

    # fallback: intenta traducir directamente si coincide con una key EN exacta
    return t



def normalize_event_title_variants(text: str) -> str:
    """
    Normaliza variantes compactas:
      - '100m' -> '100 m'
      - 'Juv Jun' -> 'Juvenil - Júnior'
      - 'Abs/Cad/Inf' -> 'Absoluto/Cadete/Infantil'
      - 'Mas/Fem/Mix' -> 'Masculino/Femenino/Mixto'
      - 'Combinada' -> 'Combinada de Salvamento' (si aplica)
      - 'Obstáculos' -> 'Natación con Obstáculos' (si aparece como disciplina sola)
    """
    if not text:
        return text

    s = normalize_spaces(text)

    # 1) Separar distancia pegada (100m / 4x50m)
    #    Mantiene "4x" tolerante a espacios
    def _unglue(m):
        tok = m.group(1)
        tok = re.sub(r"\s+", "", tok, flags=re.IGNORECASE)  # "4 x 50" -> "4x50"
        return f"{tok} m"
    s = _DISTANCE_GLUE_RE.sub(_unglue, s)

    # 2) Categorías abreviadas
    for rx, repl in _CAT_ABBR_FIXES:
        s = rx.sub(repl, s)

    # 3) Sexo abreviado
    for rx, repl in _SEX_ABBR_FIXES:
        s = rx.sub(repl, s)

    # 4) Combinada (cualquier variante) -> 'Combinada de Salvamento' (solo si aparece como disciplina)
    #    Si ya viene con 'de Salvamento', no cambia.
    if re.search(r"\bcombinada\b", s, re.IGNORECASE):
        # normaliza "Combinada Salvamento" -> "Combinada de Salvamento"
        s = re.sub(r"\bcombinada\s+salvamento\b", "Combinada de Salvamento", s, flags=re.IGNORECASE)
        s = re.sub(r"\bcombinada\b(?!\s+de\s+salvamento)", "Combinada de Salvamento", s, flags=re.IGNORECASE)

    # 5) Obstáculos como disciplina abreviada
    #    Si aparece solo "Obstáculos" (o "Natación Obstáculos"), lo llevamos a "Natación con Obstáculos"
    s = re.sub(r"\bnataci[oó]n\s+obst[aá]culos\b", "Natación con Obstáculos", s, flags=re.IGNORECASE)
    s = re.sub(r"\bobst[aá]culos\b", "Natación con Obstáculos", s, flags=re.IGNORECASE)

    # 6) Normaliza "Lanzamiento cuerda" a "Lanzamiento de cuerda"
    s = re.sub(r"\blanzamiento\s+cuerda\b", "Lanzamiento cuerda", s, flags=re.IGNORECASE)

    return normalize_spaces(s)


# -------------------------------------
# --- MAIN CODE
# -------------------------------------
def build_event_fields(event_title: str, category_line: Optional[str]) -> Dict:
    """
    Construye:
      - base: "<distancia> <disciplina ES>" (la distancia SI va aquí)
      - discipline: NO se devuelve aquí (la calcula parser.py desde base),
        pero base queda ya en ES canónico para que discipline también lo sea.
      - distance_m: "200" / "4x50" etc.
      - category, sex, relay, id
    """
    # -------------------------------------
    # --- EVENT TITLE
    # -------------------------------------
    raw_title = normalize_event_title_variants(event_title or "")
    raw_title = _fix_glued_tokens(raw_title)

    # --- LIMPIEZA: eliminar sufijos editoriales que NO deben influir en sexo/categoría
    # (Relevos) / Relevos / (Relevo) etc.
    raw_title = re.sub(r"\(\s*relevos?\s*\)", "", raw_title, flags=re.IGNORECASE)
    raw_title = re.sub(r"\brelevos?\b", "", raw_title, flags=re.IGNORECASE)
    raw_title = normalize_spaces(raw_title)

    # --- LIMPIEZA: el PDF a veces añade un "máster" redundante al final:
    # "máster R4 +170 F máster" -> "máster R4 +170 F"
    raw_title = re.sub(r"\b([MFxX])\s+m[áa]ster\b\s*$", r"\1", raw_title, flags=re.IGNORECASE)
    raw_title = normalize_spaces(raw_title)

    # FIX: elimina "máster" duplicado en títulos tipo
    # "Máster R4 +170 F máster"
    raw_title = _DUPLICATE_TRAILING_MASTER_RE.sub(r"\1", raw_title)
    raw_title = normalize_spaces(raw_title)

    # FIX PDF 2023Esp: título pegado a "Finales - Results ..." y a veces "AgrupadaFinales"
    raw_title = re.sub(
        r"\b(Agrupad[oa])(?=(Finales|Resultados|Results)\b)",
        r"\1 ",
        raw_title,
        flags=re.IGNORECASE
    )
    raw_title = re.split(r"\b(?:Finales|Resultados|Results)\b", raw_title, 1)[0].strip()

    # Limpieza editorial (SIEMPRE)
    raw_title = re.sub(r"\bagrupad[oa]\b", "", raw_title, flags=re.IGNORECASE)
    raw_title = normalize_spaces(raw_title)
    raw_title = collapse_duplicate_words(raw_title)

    # --- SEXO: en relays máster suele venir como "... R4 +170 M" o "... +200 F"
    sex_from_title = None
    m_sex_after_sum = re.search(r"\+\s*\d{3}\s*([MFxX])\b", raw_title, flags=re.IGNORECASE)
    if m_sex_after_sum:
        sex_from_title = m_sex_after_sum.group(1).upper()
        # NO quitamos la letra del título aquí (solo la capturamos). Ya has eliminado "(Relevos)" y "máster" final.

    # Sexo puede venir como letra al final del título
    sex_from_title, raw_title_wo_sex = _extract_trailing_sex_letter(raw_title)
    if sex_from_title:
        raw_title = raw_title_wo_sex

    # Sexo inline: "<prueba> F Agrupada" -> ('F', '<prueba>')
    sex_inline, raw_title_wo_inline = _extract_inline_sex_letter(raw_title)
    if sex_inline:
        sex_from_title = sex_inline
        raw_title = raw_title_wo_inline

    # Sexo desde category_line (si existe) también puede venir como "... F"
    sex_from_cat = None
    if category_line:
        category_line = collapse_duplicate_words(category_line)
        category_line = _fix_glued_tokens(category_line)
        sex_from_cat, cat_wo_sex = _extract_trailing_sex_letter(category_line)
        if sex_from_cat:
            category_line = cat_wo_sex

    # tramo ES tras el guion si existe (solo si es separador EN - ES, NO si es "Juvenil - Júnior")
    es_part = raw_title
    if re.search(r"\s-\s", raw_title) and not JUV_JUN_RE.search(raw_title):
        left, right = re.split(r"\s-\s", raw_title, 1)
        # split solo si a la izquierda hay pinta de inglés (evita falsos positivos)
        if re.search(r"\b(obstacle|manikin|lifesaver|rescue|relay|line throw)\b", left, re.IGNORECASE):
            es_part = right.strip()

    es_part = collapse_duplicate_words(es_part)
    master_display, base_source = extract_master_category_and_trim(es_part)

    # -------------------------------------
    # --- CATEGORY LINE
    # -------------------------------------
    cat = None
    sex_source = " ".join([raw_title, es_part, category_line or ""])
    sx = sex_code(sex_source)

    if category_line:
        cat_candidate = None
        category_line = normalize_event_title_variants(category_line)
        category_line = _fix_glued_tokens(category_line)

        m = CATEGORY_LINE_RE.match(category_line)
        if m:
            cat_text = m.group(1).strip()            
            cat_text = _strip_trailing_master(cat_text)
            cat_text = collapse_duplicate_words(cat_text)

            sex_text = m.group(2).strip()

            # Caso MásterR4 +xxx: úsalo como master_display explícito
            if re.match(r"^master\\s*r4\\s*\\+\\s*\\d{3}$", normalize_key(cat_text), flags=0):
                cat = master_category_to_canonical(cat_text.replace("Master", "Máster"))
                cat_display_override = _normalize_master_display(cat_text.replace("Master", "Máster"))
            else:
                cat_candidate = category_code(cat_text) or cat
                if cat_candidate:
                    cat = cat_candidate

            sx_candidate = sex_code(sex_text)
            if sx_candidate != "X":
                sx = sx_candidate
            if cat_candidate:
                cat = cat_candidate

    if not sx:
        sx = sex_code(raw_title)

    cat_display_override = None
    if not cat:
        if master_display and (not _is_multi_master_display(master_display)):
            cat = master_category_to_canonical(master_display)
            cat_display_override = _normalize_master_display(master_display)
        else:
            cat = category_code(raw_title)

    if not cat:
        cat = "absoluto"

    # -------------------------------------
    # --- RELEVOS / DISTANCIA / TRADUCCIÓN
    # -------------------------------------
    # Mejora mínima: detectar "relay" en inglés también (no rompe los casos ES)
    relay_hint = normalize_spaces(f"{raw_title} {es_part}")

    # Lanzamiento de cuerda: sin distancia
    if is_line_throw(es_part) or is_line_throw(raw_title):
        discipline_es = "Lanzamiento de Cuerda"
        distance_m = None
        prefix = None
        base = discipline_es
        canonical_key = "line throw"
        relay = True
    else:
        # 1) Distancia si viene en el título (da igual EN/ES y orden)
        prefix, distance_m = extract_distance_from_title(raw_title)
        if not distance_m:
            prefix, distance_m = extract_distance_from_title(es_part)

        # 2) Texto base para disciplina (sin cat/sex)        
        full_src = base_source if master_display else es_part
        kfull = normalize_key(full_src)
        rubber_fins = ("remolque" in kfull and "aletas" in kfull and ("infantil" in kfull or re.search(r"\binf\b", kfull)))

        rest_src = strip_category_sex_es(base_source if master_display else es_part)
        rest_src = normalize_spaces(rest_src)

        # Si el texto trae distancia al inicio, la quitamos para no duplicar
        rest_src = re.sub(
            r"^(?:4\s*x\s*)?\d+(?:[.,]\d+)?\s*(?:\u202F|\s)?m?\.?\s*",
            "",
            rest_src,
            flags=re.IGNORECASE
        ).strip()

        # 3) Canonicalización EN/ES -> key EN canónica
        if rubber_fins:
            canonical_key = "manikin carry with rubber fins"
        else:
            canonical_key = canonicalize_event_key(rest_src)

        relay_hint = normalize_spaces(f"{raw_title} {es_part}")
        relay = (
            canonical_key.strip().lower().endswith("relay")
            or ("4x" in relay_hint.lower())
            or bool(re.search(r"\brelevo\b", relay_hint.lower()))
            or bool(re.search(r"\brelay\b", relay_hint.lower()))
        )

        # 4) Traducción estable a ES (discipline sin distancia)
        discipline_es = translate_event_name_es(canonical_key)
        if not discipline_es or discipline_es == canonical_key:
            # fallback: si no hay mapping, al menos capitaliza
            discipline_es = title_case_es(rest_src)

        # 5) Distancia por defecto si NO venía en el título
        if not distance_m:
            dflt = DEFAULT_EVENT_DISTANCE_M.get(canonical_key)
            if dflt:
                # dflt puede venir como "200" o "4x50"
                if dflt.lower().startswith("4x"):
                    num = dflt[2:]
                    prefix, distance_m = _normalize_distance_prefix(True, num)
                else:
                    prefix, distance_m = _normalize_distance_prefix(False, dflt)

        # 6) Forzar "Relevo " si es relay y el nombre traducido no lo trae ya
        if relay and discipline_es and not re.match(r"^\s*relevo\b", discipline_es, flags=re.IGNORECASE):
            discipline_es = f"Relevo {discipline_es}".strip()

        # 7) Construir base (base SI incluye distancia)
        if prefix:
            base = f"{prefix} {discipline_es}".strip()
        else:
            base = discipline_es.strip()

    # -------------------------------------
    # --- NORMALIZACIÓN MÁSTER R4 EN RELEVOS
    # -------------------------------------
    # Regla: si es relevo y la categoría es "master_+<tres cifras>", forzar "master_r4_+<tres cifras>"
    if relay and isinstance(cat, str) and re.fullmatch(r"master_\+\d{3}", cat):
        cat = "master_r4_" + cat.split("master_", 1)[1]   # master_+170 -> master_r4_+170

        # Asegurar también el display si venía como override o si luego sale de category_display
        # Si ya había override ("Máster +170"), lo convertimos a "Máster R4 +170"
        if cat_display_override:
            # Normaliza "Máster" y añade R4 si no estaba
            if re.search(r"\bm[áa]ster\b\s*\+\d{3}\b", cat_display_override, flags=re.IGNORECASE) and "R4" not in cat_display_override.upper():
                cat_display_override = re.sub(r"\bm[áa]ster\b", "Máster R4", cat_display_override, flags=re.IGNORECASE)
        else:
            # Si no había override, forzamos uno explícito para que el display sea estable
            # (asumiendo formato "Máster R4 +XYZ")
            m = re.search(r"\+\d{3}", cat)
            if m:
                cat_display_override = f"Máster R4 {m.group(0)}"

    # -------------------------------------
    # --- SEX / ID
    # -------------------------------------
    sex_letter = sex_from_cat or sex_from_title
    if sex_letter in {"F", "M", "X"}:
        sex = sex_letter
    else:
        sex = sx  # F/M/X

    category = cat  # juvenil/junior/absoluto/master_...
    event_id = "e_" + slugify(f"{base}_{category}_{sex}").lower()

    raw_cat_display = cat_display_override if cat_display_override else category_display(category)

    debug_info = None
    if "máster" in (event_title or "").lower() or "master" in (event_title or "").lower():
        debug_info = {
            "raw_title": raw_title,
            "es_part": es_part,
            "master_display": master_display,
            "category_line": category_line,
            "cat": cat,
            "sex": sx,
            "base": base,
            "distance_m": distance_m,
            "relay": relay,
            "id": event_id,
            "canonical_key": canonical_key,
        }

    return {
        "base": base,
        "distance_m": distance_m,
        "relay": relay,
        "category": category,
        "category_display": _normalize_category_display_es(raw_cat_display),
        "sex": sex,
        "id": event_id,
        "debug_info": debug_info,
    }