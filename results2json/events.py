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
SEX_WORDS_RE = re.compile(r"\b(masculino|masculina|femenino|femenina|mixto|mixta)\b", re.IGNORECASE)

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

SEX_TAIL_RE = re.compile(r"\b(femen\w*|mascul\w*|mixt\w*)\b", re.IGNORECASE)

# Detecta distancia en cualquier parte (EN o ES), tolerante:
# - "200m", "200 m", "200 m.", "200" (sin m), "200 m"
# - "4x50m", "4x50 m", "4 x 50 m", "4x12,5m", "4x12.5 m", "4x12,5"
DIST_ANY_RE = re.compile(
    r"(?P<relay>4\s*x)\s*(?P<num>\d+(?:[.,]\d+)?)\s*(?:\u202F|\s)?m?\.?\b"
    r"|(?P<num2>\d{2,3})\s*(?:\u202F|\s)?m?\.?\b",
    re.IGNORECASE
)

CATEGORY_LINE_RE = re.compile(r"^\s*(.+?)\s*\((.+?)\)\s*$", re.IGNORECASE)

EVENT_NAME_ES = {
    "line throw": "Lanzamiento de Cuerda",
    "obstacle swim": "Natación con Obstáculos",
    "obstacle relay": "Relevo Natación con Obstáculos",
    "manikin carry": "Arrastre de Maniquí",
    "manikin relay": "Relevo Arrastre de Maniquí",
    "medley relay": "Relevo Combinado",
    "super lifesaver": "Supersocorrista",
    "manikin tow with fins": "Socorrista",
    "manikin carry with fins": "Arrastre de Maniquí con Aletas",
    "rescue medley": "Combinada de Salvamento",
    "pool lifesaver relay": "Relevo Socorrista"
}

DEFAULT_EVENT_DISTANCE_M = {
    "obstacle swim": "200",
    "obstacle relay": "4x50",
    "natación con obstáculos": "200",
    "relevo natación con obstáculos": "4x50",
    "manikin tow with fins": "100",
    "socorrista": "100",
    "manikin carry with fins": "100",
    "arrastre de maniquí con aletas": "100",
    "manikin carry": "50",
    "arrastre de maniquí": "50",
    "rescue medley": "100",
    "pool lifesaver relay": "4x50",
    "manikin relay": "4x25",
    "relevo remolque de maniquí": "4x25",
    "relevo arrastre de maniquí": "4x25",
    "super lifesaver": "200",
    "supersocorrista": "200",
    "medley relay": "4x50",
    "relevo combinado": "4x50",
    # Añade aquí más disciplinas según tus necesidades
}

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
    return ("line throw" in t) or ("lanzamiento de cuerda" in t)


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


def category_code(raw: Optional[str]) -> str:
    r = (raw or "").lower()


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

    # Categorías invariables en género
    if cat in {"infantil", "juvenil", "junior"}:
        return cat.capitalize()

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
        return f"Máster R4 {val}"

    # Máster rangos / sumas
    if cat.startswith("master_"):
        val = cat.split("master_", 1)[1].replace("_", "")
        return f"Máster {val}"

    # Fallback defensivo
    return "Absoluta"


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
    seg = re.sub(r"\bma[áa]ster\s*r4\b", "Máster R4", seg, flags=re.IGNORECASE)
    seg = re.sub(r"\bma[áa]sterr4\b", "Máster R4", seg, flags=re.IGNORECASE)

    # asegurar "Máster" con acento al inicio
    seg = re.sub(r"^ma[áa]ster", "Máster", seg, flags=re.IGNORECASE)

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
    """
    Busca distancia en cualquier parte del título (EN o ES), tolerante:
      - 200m / 200 m / 200 m. / 200 (sin 'm')
      - 4x50m / 4x12,5m / 4 x 12.5 m / 4x12,5 (sin 'm')
    Devuelve (prefix_text, distance_m) usando el formato ES:
      prefix_text: "200\u202Fm" / "4x12,5\u202Fm"
      distance_m:  "200" / "4x12,5"
    """
    s = event_title or ""
    m = DIST_ANY_RE.search(s)
    if not m:
        return None, None

    # Relevo: 4x...
    if m.group("relay") and m.group("num"):
        # normaliza "4 x" -> relay True
        return _normalize_distance_prefix(True, m.group("num"))

    # Individual: 50/100/200...
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
    if "manikin tow with fins" in t:
        return "manikin tow with fins"
    if "manikin carry" in t:
        return "manikin carry"
    if "manikin carry with fins" in t:
        return "manikin carry with fins"
    if "manikin relay" in t:
        return "manikin relay"
    if "line throw" in t:
        return "line throw"
    if "obstacle relay" in t:
        return "obstacle relay"
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
    if "arrastre de maniqui con aletas" in t:
        return "manikin tow with fins"
    if t == "arrastre de maniqui" or "remolque de maniqui" in t:
        return "manikin carry"
    if t == "arrastre de maniqui con aletas" or "remolque de maniqui con aletas" in t:
        return "manikin carry with fins"
    if "socorrista" in t:
        return "manikin tow with fins"
    if t == "relevo arrastre de maniqui" or "relevo remolque de maniqui" in t:
        return "manikin relay"
    if "lanzamiento de cuerda" in t:
        return "line throw"
    if "relevo natacion con obstaculos" in t:
        return "obstacle relay"
    if "supersocorrista" in t:
        return "super lifesaver"
    if "combinada de salvamento" in t:
        return "rescue medley"
    if "relevo combinado" in t:
        return "medley relay"
    if "relevo socorrista" in t:
        return "pool lifesaver relay"

    # fallback: intenta traducir directamente si coincide con una key EN exacta
    return t


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
    raw_title = event_title or ""
    raw_title = _fix_glued_tokens(raw_title)

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
        category_line = _fix_glued_tokens(category_line)
        sex_from_cat, cat_wo_sex = _extract_trailing_sex_letter(category_line)
        if sex_from_cat:
            category_line = cat_wo_sex

    # tramo ES tras guion si existe (si viene "EN - ES")
    es_part = raw_title
    if re.search(r"\s-\s", raw_title):
        es_part = re.split(r"\s-\s", raw_title, 1)[1].strip()

    master_display, base_source = extract_master_category_and_trim(es_part)

    # -------------------------------------
    # --- CATEGORY LINE
    # -------------------------------------
    cat = None
    sex_source = " ".join([raw_title, es_part, category_line or ""])
    sx = sex_code(sex_source)

    if category_line:
        m = CATEGORY_LINE_RE.match(category_line)
        if m:
            cat_candidate = category_code(m.group(1)) or cat
            sx_candidate = sex_code(m.group(2))
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
            cat_display_override = master_display
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
        canonical_key = canonicalize_event_key(rest_src)

        relay_hint = normalize_spaces(f"{raw_title} {es_part}")
        relay = (
            canonical_key.strip().lower().endswith("relay")
            or bool(re.search(r"\b4x\b", relay_hint.lower()))
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
    # --- SEX / ID
    # -------------------------------------
    sex_letter = sex_from_cat or sex_from_title
    if sex_letter in {"F", "M", "X"}:
        sex = sex_letter
    else:
        sex = sx  # F/M/X

    category = cat  # juvenil/junior/absoluto/master_...
    event_id = "e_" + slugify(f"{base}_{category}_{sex}").lower()

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
        "category_display": cat_display_override if cat_display_override else category_display(category),
        "sex": sex,
        "id": event_id,
        "debug_info": debug_info,
    }