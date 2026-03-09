from __future__ import annotations

import re
from typing import List, Tuple, Optional, Dict, Any

from .normalize import (
    normalize_spaces,
    normalize_dashes,
    normalize_title,
    normalize_pool,
    strip_accents,
)

# ----------------------------
# Regex y constantes
# ----------------------------

MONTHS_ES = {
    "enero": "01", "febrero": "02", "marzo": "03",
    "abril": "04", "mayo": "05", "junio": "06",
    "julio": "07", "agosto": "08", "septiembre": "09", "setiembre": "09",
    "octubre": "10", "noviembre": "11", "diciembre": "12"
}
MONTHS_EN = {
    "january": "01", "february": "02", "march": "03",
    "april": "04", "may": "05", "june": "06",
    "july": "07", "august": "08", "september": "09",
    "october": "10", "november": "11", "december": "12"
}

DATE_RE = re.compile(
    r"(?P<d1>\d{1,2})\s*(?:de)?\s*(?P<m>[a-záéíóúñ]+)\s*(?:de)?\s*(?P<y>\d{4})",
    re.IGNORECASE
)
RANGE_RE = re.compile(
    r"(?P<d1>\d{1,2})\s*(?:-|al|a)\s*(?P<d2>\d{1,2})\s+de\s+(?P<m>[a-záéíóúñ]+)\s+(?P<y>\d{4})",
    re.IGNORECASE
)

DATE_EN_RE = re.compile(
    r"\b(?P<d>\d{1,2})(?:st|nd|rd|th)?\s+(?P<m>[A-Za-z]+)\s+(?P<y>\d{4})\b",
    re.IGNORECASE
)
DATE_ES_NOYEAR_RE = re.compile(
    r"\b(?P<d>\d{1,2})\s*(?:de\s+)?(?P<m>[a-záéíóúñ]+)\b",
    re.IGNORECASE
)
# TODO Problema entendiendo cabeceras. El un fichero tipo 202502master, no toma la fecha cuando aparece como "ARGANDA \n 30 noviembre 2024 (Piscina/Pool: 25 M)" en la cabecera
# TODO Problema entendiendo cabeceras. El un fichero tipo 202502master, no calcula la temporada cuando aparece como "ARGANDA \n 30 noviembre 2024 (Piscina/Pool: 25 M)" en la cabecera

# ----------------------------
# Cabecera: detección
# ----------------------------

def is_header_start(line: str) -> bool:
    u = normalize_spaces(line).upper()
    return (
        u.startswith("RESULTADOS") or
        u.startswith("RESULTS") or
        u.startswith("FINAL RESULTS") or
        u.startswith("RESULTADOS FINAL") or
        u.startswith("RESULTADOS DEFINITIVOS") or
        u.startswith("DEFINITIVE RESULTS")
    )


def is_ordinal_only_line(line: str) -> bool:
    """
    Detecta líneas que solo contienen sufijos ordinales ingleses:
    'st', 'nd', 'rd', 'th' (posiblemente repetidos, con espacios).
    """
    if not line:
        return False
    s = normalize_spaces(line).lower()
    return bool(re.fullmatch(r"(st|nd|rd|th)(\s+(st|nd|rd|th))*", s))


def is_date_line(line: str) -> bool:
    ln = normalize_dashes(line)
    # ES con año / ES compacto
    if DATE_RE.search(ln.lower()) or RANGE_RE.search(ln.lower()):
        return True
    # EN
    if DATE_EN_RE.search(ln):
        return True
    # mixto EN/ES separado por "/"
    if "/" in ln:
        left = ln.split("/", 1)[0]
        if DATE_EN_RE.search(left) or DATE_RE.search(ln.lower()):
            return True
    return False


def extract_header_lines(pdf, debug: bool = False) -> List[str]:
    """
    Devuelve las líneas de cabecera detectadas (desde RESULTADOS hasta la línea de fecha).
    """
    for page_idx, page in enumerate(pdf.pages, start=1):
        text = page.extract_text()
        if debug:
            print(f"DEBUG page {page_idx}: extract_text length =", 0 if not text else len(text))
        if not text:
            continue

        lines = [normalize_spaces(l) for l in text.split("\n") if l.strip()]
        for i, ln in enumerate(lines):
            if is_header_start(ln):
                header: List[str] = []
                for j in range(i, len(lines)):
                    header.append(lines[j])
                    if is_date_line(lines[j]):
                        if debug:
                            print("DEBUG cabecera real detectada:")
                            for x in header:
                                print(" ", x)
                        return header

                # fallback: si no detecta fecha, devuelve primeras líneas tras RESULTADOS
                if debug:
                    print("DEBUG cabecera (sin fecha detectada, fallback):")
                    for x in lines[i:i+12]:
                        print(" ", x)
                return lines[i:i+12]

    return []


# ----------------------------
# Fechas
# ----------------------------

def parse_date_en(text: str) -> Optional[str]:
    m = DATE_EN_RE.search(text)
    if not m:
        return None
    d = int(m.group("d"))
    mm = MONTHS_EN.get(m.group("m").lower(), "")
    y = m.group("y")
    if not mm:
        return None
    return f"{y}-{mm}-{d:02d}"


def parse_range_en(text: str) -> Tuple[Optional[str], Optional[str]]:
    text = normalize_dashes(text.strip())
    parts = [p.strip() for p in re.split(r"\s*-\s*", text, maxsplit=1)]
    if len(parts) != 2:
        return None, None
    a = parse_date_en(parts[0])
    b = parse_date_en(parts[1])
    return a, b


def parse_range_es_no_year(text: str):
    text = normalize_dashes(text.strip().lower())
    parts = [p.strip() for p in re.split(r"\s*-\s*", text, maxsplit=1)]
    if len(parts) != 2:
        return None, None

    m1 = DATE_ES_NOYEAR_RE.search(parts[0])
    m2 = DATE_ES_NOYEAR_RE.search(parts[1])
    if not m1 or not m2:
        return None, None

    d1 = int(m1.group("d"))
    mon1 = strip_accents(m1.group("m").lower())
    d2 = int(m2.group("d"))
    mon2 = strip_accents(m2.group("m").lower())
    if mon2.isdigit() or mon2 in {"", None}:
        mon2 = mon1
    return (d1, mon1), (d2, mon2)


def parse_dates(text: str, debug: bool = False) -> Tuple[Optional[str], Optional[str]]:
    """
    Soporta:
      - rango mixto EN/ES: '02nd May 2025 - 04th May 2025 / 2 de mayo - 4 de mayo'
      - rango ES completo: '15 noviembre 2025 - 16 noviembre 2025'
      - rango ES compacto: '15-16 de noviembre 2025'
      - fecha única ES/EN
    """
    raw = text
    text = normalize_dashes(text.lower().strip())
    if debug:
        print("DEBUG parse_dates input:", raw)
        print("DEBUG parse_dates normalized:", text)

    # Caso 0: mixto EN / ES
    if "/" in text:
        left, right = [t.strip() for t in text.split("/", 1)]
        en_start, en_end = parse_range_en(left)
        if debug:
            print("DEBUG EN range:", en_start, en_end)
        if en_start and en_end:
            year = en_start[:4]
            es_start_pair, es_end_pair = parse_range_es_no_year(right)
            if debug:
                print("DEBUG ES range (no year):", es_start_pair, es_end_pair)
            if es_start_pair and es_end_pair:
                d1, mon1 = es_start_pair
                d2, mon2 = es_end_pair
                mm1 = MONTHS_ES.get(mon1, "")
                mm2 = MONTHS_ES.get(mon2, "")
                if mm1 and mm2:
                    return f"{year}-{mm1}-{d1:02d}", f"{year}-{mm2}-{d2:02d}"
            return en_start, en_end

    # Caso 1: rango ES con dos fechas completas
    parts = [p.strip() for p in re.split(r"\s*-\s*", text, maxsplit=1)]
    if len(parts) == 2:
        left, right = parts
        d1 = DATE_RE.search(left)
        d2 = DATE_RE.search(right)
        if d1 and d2:
            m1 = strip_accents(d1.group("m"))
            m2 = strip_accents(d2.group("m"))
            mm1 = MONTHS_ES.get(m1, "")
            mm2 = MONTHS_ES.get(m2, "")
            if mm1 and mm2:
                date_start = f"{d1.group('y')}-{mm1}-{int(d1.group('d1')):02d}"
                date_end = f"{d2.group('y')}-{mm2}-{int(d2.group('d1')):02d}"
                return date_start, date_end

    # Caso 2: rango ES compacto
    m_range = RANGE_RE.search(text)
    if m_range:
        mm = MONTHS_ES.get(strip_accents(m_range.group("m")), "")
        y = m_range.group("y")
        d1 = int(m_range.group("d1"))
        d2 = int(m_range.group("d2"))
        if mm:
            return f"{y}-{mm}-{d1:02d}", f"{y}-{mm}-{d2:02d}"

    # Caso 3: fecha única ES
    m_single = DATE_RE.search(text)
    if m_single:
        mm = MONTHS_ES.get(strip_accents(m_single.group("m")), "")
        y = m_single.group("y")
        d = int(m_single.group("d1"))
        if mm:
            return f"{y}-{mm}-{d:02d}", None

    # Caso 4: fecha única EN
    en_single = parse_date_en(text)
    if en_single:
        return en_single, None

    return None, None


# ----------------------------
# Competition
# ----------------------------

def parse_location_region(loc_line: str, debug: bool = False) -> Tuple[str, str]:
    """
    Soporta:
      - 'Ciudad (Región)' -> (Ciudad, Región)
      - 'Ciudad, Región' -> (Ciudad, Región)
      - 'Ciudad' -> (Ciudad, "")
    """
    if not loc_line:
        return "", ""
    loc_line = normalize_spaces(loc_line).strip()

    m = re.match(r"^(?P<loc>.+?)\s*\((?P<reg>[^()]+)\)\s*$", loc_line)
    if m:
        location = normalize_title(m.group("loc").strip())
        region = normalize_title(m.group("reg").strip())
        return location, region

    if "," in loc_line:
        a, b = [x.strip() for x in loc_line.split(",", 1)]
        return normalize_title(a), normalize_title(b)

    return normalize_title(loc_line), ""


def parse_competition_from_header(lines: List[str], debug: bool = False) -> Dict[str, Any]:
    """
    Devuelve dict competition con:
      name, name_clean, location, region, pool_type, date_start, date_end, date
    """
    if not lines:
        raise ValueError("Cabecera vacía: extract_header_lines no devolvió líneas")

    # buscar línea con fecha
    date_idx = None
    for i, ln in enumerate(lines):
        if DATE_RE.search(ln.lower()) or RANGE_RE.search(ln.lower()) or DATE_EN_RE.search(ln):
            date_idx = i
            break
    if date_idx is None:
        raise ValueError("No se ha encontrado línea de fecha en la cabecera")

    date_line = lines[date_idx]

    # piscina (si viene entre paréntesis)
    pool_type = ""
    m_pool = re.search(r"\(([^)]+)\)", date_line)
    if m_pool:
        pool_raw = m_pool.group(1)
        m_size = re.search(r"(25|50)\s*[EM]", pool_raw.upper())
        if m_size:
            pool_type = normalize_pool(m_size.group(0))
        date_line = date_line.replace(m_pool.group(0), "").strip()

    date_start, date_end = parse_dates(date_line, debug=debug)

    # localización: línea anterior real (saltando ordinal-only)
    loc_idx = date_idx - 1
    while loc_idx >= 0 and is_ordinal_only_line(lines[loc_idx]):
        loc_idx -= 1
    location, region = ("", "")
    if loc_idx >= 0:
        location, region = parse_location_region(lines[loc_idx], debug=debug)

    # nombre: desde la línea 1 hasta antes de la localización real
    name_lines = lines[1:loc_idx] if loc_idx > 1 else []
    name_lines = [ln for ln in name_lines if not is_ordinal_only_line(ln)]
    name = normalize_title(" ".join(name_lines))

    # name_clean (si no tienes reglas específicas, usa name)
    name_clean = name

    return {
        "name": name,
        "name_clean": name_clean,
        "location": location,
        "region": region,
        "pool_type": pool_type,
        "date_start": date_start,
        "date_end": date_end,
        "date": date_start,
    }


# ----------------------------
# Season
# ----------------------------

def season_end_year_from_date_iso(date_iso: str) -> Optional[int]:
    """
    Regla Oct–Sep:
      - Oct/Nov/Dec => end_year = year + 1
      - Jan..Sep    => end_year = year
    """
    if not date_iso:
        return None
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", date_iso.strip())
    if not m:
        return None
    yyyy, mm, _ = map(int, m.groups())
    return yyyy + 1 if mm >= 10 else yyyy


def season_label_from_end_year(end_year: int) -> str:
    start_year = end_year - 1
    return f"Temporada {start_year}-{end_year}"


def season_id_from_label(label: str) -> str:
    m = re.search(r"(\d{4})-(\d{4})", label)
    if not m:
        return "s_unknown"
    a, b = m.groups()
    return f"s_{a}_{b}"


def infer_season_label_from_text(text: str) -> Optional[str]:
    """
    Busca temporada explícita:
      - 'Temporada 24-25' -> 'Temporada 2024-2025'
      - '2024-2025' -> 'Temporada 2024-2025'
    """
    if not text:
        return None
    t = text.lower()

    m = re.search(r"\btemporada\s*(\d{2})\s*[-/]\s*(\d{2})\b", t)
    if m:
        a, b = m.groups()
        return f"Temporada 20{a}-20{b}"

    m = re.search(r"\b(20\d{2})\s*[-/]\s*(20\d{2})\b", t)
    if m:
        a, b = m.groups()
        return f"Temporada {a}-{b}"

    return None


def parse_season_from_header(header_lines: List[str], competition: Optional[Dict[str, Any]] = None, debug: bool = False) -> Dict[str, Any]:
    """
    Devuelve dict season:
      {id, label, end_year, rule, source}
    Prioridad:
      1) por date_start (más fiable)
      2) por temporada explícita en texto
      3) unknown
    """
    date_iso = None
    if competition and isinstance(competition, dict):
        date_iso = competition.get("date_start") or competition.get("date")

    if date_iso:
        end_year = season_end_year_from_date_iso(date_iso)
        if end_year:
            label = season_label_from_end_year(end_year)
            sid = season_id_from_label(label)
            return {
                "id": sid,
                "label": label,
                "end_year": end_year,
                "rule": "Oct-01..Sep-30 => season_end_year",
                "source": "date"
            }

    text = " ".join(header_lines or [])
    explicit = infer_season_label_from_text(text)
    if explicit:
        sid = season_id_from_label(explicit)
        return {
            "id": sid,
            "label": explicit,
            "end_year": None,
            "rule": "explicit-in-header",
            "source": "header"
        }

    return {
        "id": "s_unknown",
        "label": "Temporada (desconocida)",
        "end_year": None,
        "rule": "unknown",
        "source": "none"
    }