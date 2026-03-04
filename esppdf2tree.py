#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from doctest import debug
import os
import re
import json
import argparse
import unicodedata
import pdfplumber
from datetime import datetime
from glob import glob

# ----------------------------
# Normalización
# ----------------------------
def normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

def strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )

def normalize_title(s: str) -> str:
    """
    Title Case controlado, mantiene números romanos en mayúscula
    """
    if not s:
        return ""
    words = s.split()
    out = []
    for w in words:
        if re.fullmatch(r"[IVXLCDM]+", w.upper()):
            out.append(w.upper())
        else:
            out.append(w.capitalize())
    return " ".join(out)

def normalize_pool(pool_raw: str) -> str:
    pool_raw = pool_raw.replace(" ", "").upper()
    if pool_raw in {"25M", "25E", "50M", "50E"}:
        return pool_raw
    return ""

def normalize_dashes(s: str) -> str:
    return re.sub(r"[‐‑‒–—−]", "-", s)

def normalize_key(s: str) -> str:
    s = normalize_spaces(s)
    s = strip_accents(s).lower()
    return s

def slugify(s: str) -> str:
    s = normalize_key(s)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "na"

def sanitize_name_raw(s: str) -> str:
    """Limpieza previa del texto de nombre que viene del PDF."""
    if not s:
        return ""
    s = s.replace("\u00a0", " ")               # NBSP -> space
    s = normalize_spaces(s)
    # quitar adornos típicos de PDF (asteriscos, bullets)
    s = re.sub(r"[*•·]+", "", s)
    # normalizar guiones Unicode a guion normal
    s = re.sub(r"[‐‑‒–—−]", "-", s)
    return normalize_spaces(s)

def athlete_key(name: str) -> str:
    """
    Clave fuerte para deduplicar atletas:
      - minúsculas, sin tildes, sin puntuación, sin caracteres raros
      - solo letras/números/espacios (los espacios compactados)
    """
    s = sanitize_name_raw(name)
    s = strip_accents(s).lower()
    # elimina puntuación y deja letras/números/espacios
    s = re.sub(r"[^a-z0-9\s]", "", s)
    s = normalize_spaces(s)
    return s

HEADER_KEYWORDS = (
    "resultados", "results", "final results", "socorrista", "lifeguard",
    "año/year", "club / team", "club/team", "elim.t", "final.t", "ptos", "score",
    "campeonato", "championship", "open", "cup", "pool", "piscina"
)

MONTHS_ES = {
    "enero": "01", "febrero": "02", "marzo": "03",
    "abril": "04","mayo": "05", "junio": "06",
    "julio": "07", "agosto": "08","septiembre": "09", "setiembre": "09",
    "octubre": "10", "noviembre": "11", "diciembre": "12"
}

MONTHS_EN = {
    "january":"01","february":"02","march":"03",
    "april":"04","may":"05","june":"06",
    "july":"07","august":"08","september":"09",
    "october":"10","november":"11","december":"12"
}

DATE_RE = re.compile(
    r"(?P<d1>\d{1,2})\s*(?:de)?\s*(?P<m>[a-záéíóúñ]+)\s*(?:de)?\s*(?P<y>\d{4})",
    re.IGNORECASE
)

# 02nd May 2025  |  2 May 2025
DATE_EN_RE = re.compile(
    r"\b(?P<d>\d{1,2})(?:st|nd|rd|th)?\s+(?P<m>[A-Za-z]+)\s+(?P<y>\d{4})\b",
    re.IGNORECASE
)

# 2 de mayo | 2 mayo  (sin año)
DATE_ES_NOYEAR_RE = re.compile(
    r"\b(?P<d>\d{1,2})\s*(?:de\s+)?(?P<m>[a-záéíóúñ]+)\b",
    re.IGNORECASE
)

TIME_RE = re.compile(r"\b\d{1,2}:\d{2}:\d{2}\b")  # ej 00:28:44
TIME_TOKEN_RE = re.compile(r"^\d{1,2}:\d{2}:\d{2}$")

YEAR_RE = re.compile(r"\b\d{4}\b")

STATUS_RE = re.compile(
    r"\b(Descalificado|Baja|No\s+Presentado|DNS|DNF)\b",
    re.IGNORECASE
)
STATUS_TOKENS = {
    "descalificado", "baja", "dns", "dnf",
    "no", "presentado"  # para "No Presentado"
}


RANGE_RE = re.compile(
    r"(?P<d1>\d{1,2})\s*(?:-|al|a)\s*(?P<d2>\d{1,2})\s+de\s+(?P<m>[a-záéíóúñ]+)\s+(?P<y>\d{4})",
    re.IGNORECASE
)

CLUB_START_TOKENS = {
    "club", "c.d.", "c.d.e", "cde", "c.n.", "cn", "real", "asociación", "asociacion"
}

# ----------------------------
# Fechas
# ----------------------------
def parse_date_en(text: str):
    """Devuelve yyyy-mm-dd o None"""
    m = DATE_EN_RE.search(text)
    if not m:
        return None
    d = int(m.group("d"))
    mm = MONTHS_EN.get(m.group("m").lower(), "")
    y = m.group("y")
    if not mm:
        return None
    return f"{y}-{mm}-{d:02d}"

def parse_range_en(text: str):
    """Rango EN: '02nd May 2025 - 04th May 2025'"""
    text = normalize_dashes(text.strip())
    parts = [p.strip() for p in re.split(r"\s*-\s*", text, maxsplit=1)]
    if len(parts) != 2:
        return None, None
    a = parse_date_en(parts[0])
    b = parse_date_en(parts[1])
    return a, b

def parse_range_es_no_year(text: str):
    """
    Rango ES sin año: '2 de mayo - 4 de mayo' (o variantes)
    Devuelve ( (d1, month_str), (d2, month_str) ) o (None,None)
    """
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

    # Si en la segunda parte no repiten mes (p.ej. "2 de mayo - 4"),
    # intentamos heredar el mes del primero.
    if mon2.isdigit() or mon2 in {"", None}:
        mon2 = mon1

    return (d1, mon1), (d2, mon2)

def parse_dates(text: str, debug=False):
    """
    Extiende tu parse_dates actual:
      - soporta rango EN/ES mixto:
        '02nd May 2025 - 04th May 2025 / 2 de mayo - 4 de mayo'
      - mantiene tus formatos españoles previos
    """
    raw = text
    text = normalize_dashes(text.lower().strip())

    if debug:
        print("DEBUG parse_dates input:", raw)
        print("DEBUG parse_dates normalized:", text)

    # ---- Caso 0: Mixto EN / ES ----
    # Separadores típicos: "/" o " / "
    if "/" in text:
        left, right = [t.strip() for t in text.split("/", 1)]

        # 0.1 parse rango inglés (con año)
        en_start, en_end = parse_range_en(left)
        if debug:
            print("DEBUG EN range:", en_start, en_end)

        # Si tengo EN, intento ES sin año
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

                # Si el mes ES falla, caigo al EN
                if mm1 and mm2:
                    return f"{year}-{mm1}-{d1:02d}", f"{year}-{mm2}-{d2:02d}"
                else:
                    return en_start, en_end

            # Si ES falla, devuelvo EN (mejor que None)
            return en_start, en_end

        # si no pude con EN, sigo con lógica normal (por si era otra cosa)
        # y no retorno aquí.

    # ---- Caso 1: rango con dos fechas completas en el mismo idioma ----
    # (tu caso anterior: "15 noviembre 2025 - 16 noviembre 2025")
    
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
                date_end   = f"{d2.group('y')}-{mm2}-{int(d2.group('d1')):02d}"
                if debug:
                    print("DEBUG fechas rango completo ES:", date_start, date_end)
                return date_start, date_end

    # ---- Caso 2: rango compacto ES (15-16 de noviembre 2025) ----
    m_range = RANGE_RE.search(text)
    if m_range:
        mm = MONTHS_ES.get(strip_accents(m_range.group("m")), "")
        y = m_range.group("y")
        d1 = int(m_range.group("d1"))
        d2 = int(m_range.group("d2"))
        if mm:
            if debug:
                print("DEBUG fechas rango compacto ES:", y, mm, d1, d2)
            return f"{y}-{mm}-{d1:02d}", f"{y}-{mm}-{d2:02d}"

    # ---- Caso 3: fecha única ES ----
    m_single = DATE_RE.search(text)
    if m_single:
        mm = MONTHS_ES.get(strip_accents(m_single.group("m")), "")
        y = m_single.group("y")
        d = int(m_single.group("d1"))
        if mm:
            if debug:
                print("DEBUG fecha única ES:", y, mm, d)
            return f"{y}-{mm}-{d:02d}", None

    # ---- Caso 4 (opcional): fecha única EN ----
    en_single = parse_date_en(text)
    if en_single:
        if debug:
            print("DEBUG fecha única EN:", en_single)
        return en_single, None

    return None, None

# ----------------------------
# Temporada
# ----------------------------
def season_end_year_from_date_iso(date_iso: str):
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
    # "Temporada 2025-2026" -> "s_2025_2026"
    m = re.search(r"(\d{4})-(\d{4})", label)
    if not m:
        return "s_unknown"
    a, b = m.groups()
    return f"s_{a}_{b}"

def infer_season_label_from_text(text: str):
    """
    Busca temporada explícita en el texto:
      - "Temporada 24-25" -> Temporada 2024-2025
      - "2024-2025" -> Temporada 2024-2025
    """
    if not text:
        return None
    t = text.lower()

    # 1) Temporada 24-25 / 25-26
    m = re.search(r"\btemporada\s*(\d{2})\s*[-/]\s*(\d{2})\b", t)
    if m:
        a, b = m.groups()
        return f"Temporada 20{a}-20{b}"

    # 2) 2024-2025 / 2025/2026
    m = re.search(r"\b(20\d{2})\s*[-/]\s*(20\d{2})\b", t)
    if m:
        a, b = m.groups()
        return f"Temporada {a}-{b}"

    return None

def parse_season_from_header(header_lines, competition=None, debug=False):
    """
    Devuelve dict season: {id, label, end_year, rule, source}
    Prioridad:
      1) Fecha ya parseada en competition['date_start'] (más fiable)
      2) Temporada explícita encontrada en header_lines (fallback)
    """
    # 1) Preferente: a partir de date_start ISO
    date_iso = None
    if competition and isinstance(competition, dict):
        date_iso = competition.get("date_start") or competition.get("date")

    if date_iso:
        end_year = season_end_year_from_date_iso(date_iso)
        if end_year:
            label = season_label_from_end_year(end_year)
            sid = season_id_from_label(label)
            if debug:
                print("DEBUG season (from date):", {"id": sid, "label": label, "end_year": end_year})
            return {
                "id": sid,
                "label": label,
                "end_year": end_year,
                "rule": "Oct-01..Sep-30 => season_end_year",
                "source": "date"
            }

    # 2) Fallback: buscar temporada explícita en texto cabecera
    text = " ".join(header_lines or [])
    explicit = infer_season_label_from_text(text)
    if explicit:
        sid = season_id_from_label(explicit)
        if debug:
            print("DEBUG season (explicit):", {"id": sid, "label": explicit})
        return {
            "id": sid,
            "label": explicit,
            "end_year": None,
            "rule": "explicit-in-header",
            "source": "header"
        }

    # 3) Último recurso
    if debug:
        print("DEBUG season: no detectada (fallback a unknown)")
    return {
        "id": "s_unknown",
        "label": "Temporada (desconocida)",
        "end_year": None,
        "rule": "unknown",
        "source": "none"
    }

# ----------------------------
# Cabecera PDF
# ----------------------------

def is_header_start(line: str) -> bool:
    u = normalize_spaces(line).strip().upper()
    return (
        u.startswith("RESULTADOS") or
        u.startswith("RESULTS") or
        u.startswith("FINAL RESULTS") or
        u.startswith("RESULTADOS FINAL") or
        u.startswith("RESULTADOS DEFINITIVOS") or
        u.startswith("DEFINITIVE RESULTS")
    )

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

def extract_header_lines(pdf, debug=False):
    for page_idx, page in enumerate(pdf.pages, start=1):
        text = page.extract_text()
        if debug:
            print(f"DEBUG page {page_idx}: extract_text length =", 0 if not text else len(text))
        if not text:
            continue

        lines = [normalize_spaces(l) for l in text.split("\n") if l.strip()]

        for i, ln in enumerate(lines):
            if is_header_start(ln):
                header = []
                for j in range(i, len(lines)):
                    header.append(lines[j])
                    if is_date_line(lines[j]):
                        if debug:
                            print("DEBUG cabecera real detectada:")
                            for x in header:
                                print(" ", x)
                        return header

                # fallback si no encuentra fecha: devolver algo útil (no vacío)
                if debug:
                    print("DEBUG cabecera (sin fecha detectada, fallback):")
                    for x in lines[i:i+12]:
                        print(" ", x)
                return lines[i:i+12]

    return []

def parse_competition_from_header(lines, debug=False):
    name_lines = []
    location = ""
    region = ""
    pool_type = ""
    date_start = None
    date_end = None

    if not lines:
        raise ValueError("Cabecera vacía: extract_header_lines no devolvió líneas")

    # buscamos la línea que contiene la fecha
    date_idx = None
    for i, ln in enumerate(lines):     
        if DATE_RE.search(ln.lower()) or RANGE_RE.search(ln.lower()) or DATE_EN_RE.search(ln):
            date_idx = i
            break

    if date_idx is None:
        if debug:
            print("DEBUG NO FECHA: dump de líneas (primeras 25) + detecciones")
            for k, ln in enumerate(lines[:25]):
                ln_norm = normalize_dashes(ln)
                hit_es = bool(DATE_RE.search(ln_norm.lower()) or RANGE_RE.search(ln_norm.lower()))
                hit_en = bool(DATE_EN_RE.search(ln_norm)) if "DATE_EN_RE" in globals() else False
                print(f"  {k:02d} | hit_es={hit_es} hit_en={hit_en} | {ln_norm}")
        raise ValueError("No se ha encontrado línea de fecha en la cabecera")

    date_line = lines[date_idx]

    # piscina
    m_pool = re.search(r"\(([^)]+)\)", date_line)
    if m_pool:
        pool_raw = m_pool.group(1)

        # Extraer solo "25 E", "25 M", etc.
        m_size = re.search(r"(25|50)\s*[EM]", pool_raw.upper())
        if m_size:
            pool_type = normalize_pool(m_size.group(0))

        date_line = date_line.replace(m_pool.group(0), "").strip()

    date_start, date_end = parse_dates(date_line, debug=debug)

    # localización = línea inmediatamente anterior "real" (saltando ordinal-only)
    loc_idx = date_idx - 1
    while loc_idx >= 0 and is_ordinal_only_line(lines[loc_idx]):
        if debug:
            print("DEBUG skipping ordinal-only line for location:", lines[loc_idx])
        loc_idx -= 1
    if loc_idx >= 0:
        location, region = parse_location_region(lines[loc_idx], debug=debug)

    # nombre = desde la línea 1 hasta antes de la localización real (loc_idx)
    name_lines = lines[1:loc_idx]
    # filtra por si hubiera alguna ordinal en medio (por seguridad)
    name_lines = [ln for ln in name_lines if not is_ordinal_only_line(ln)]
    name = normalize_title(" ".join(name_lines))

    if debug:
        print("DEBUG competition name:", name)
        print("DEBUG location:", location)
        print("DEBUG region:", region)
        print("DEBUG pool:", pool_type)
        print("DEBUG date_start:", date_start)
        print("DEBUG date_end:", date_end)

    return {
        "name": name,
        "location": location,
        "region": region,
        "pool_type": pool_type,
        "date_start": date_start,
        "date_end": date_end,
        "date": date_start
    }

def is_ordinal_only_line(line: str) -> bool:
    """
    Detecta líneas que solo contienen sufijos ordinales ingleses:
    'st', 'nd', 'rd', 'th' (posiblemente repetidos, con espacios).
    Ej: "nd th"
    """
    if not line:
        return False
    s = normalize_spaces(line).lower()
    return bool(re.fullmatch(r"(st|nd|rd|th)(\s+(st|nd|rd|th))*", s))

def parse_location_region(loc_line: str, debug=False):
    """
    Soporta:
      - 'Ciudad (Región)'  -> (Ciudad, Región)
      - 'Ciudad, Región'   -> (Ciudad, Región)
      - 'Ciudad'           -> (Ciudad, "")
    """
    if not loc_line:
        return "", ""

    loc_line = normalize_spaces(loc_line).strip()

    # 1) Ciudad (Región)
    m = re.match(r"^(?P<loc>.+?)\s*\((?P<reg>[^()]+)\)\s*$", loc_line)
    if m:
        location = normalize_title(m.group("loc").strip())
        region = normalize_title(m.group("reg").strip())
        if debug:
            print("DEBUG location parsed (paren):", location, "| region:", region)
        return location, region

    # 2) Ciudad, Región
    if "," in loc_line:
        a, b = [x.strip() for x in loc_line.split(",", 1)]
        location = normalize_title(a)
        region = normalize_title(b)
        if debug:
            print("DEBUG location parsed (comma):", location, "| region:", region)
        return location, region

    # 3) Solo ciudad
    location = normalize_title(loc_line)
    if debug:
        print("DEBUG location parsed (solo):", location)
    return location, ""

# ----------------------------
# CLUBES
# ----------------------------

def clean_club_name(raw: str) -> str:
    """
    Limpia el nombre del club:
      - elimina cualquier '(...)' AL FINAL (categoría, p.ej. '(absoluta)')
      - compacta espacios
    """
    if not raw:
        return ""
    s = normalize_spaces(raw)

    # Quitar paréntesis finales repetidos: "Club X (absoluta)" -> "Club X"
    s = re.sub(r"\s*\([^()]*\)\s*$", "", s).strip()
    return s

STATUS_TOKENS = {
    "descalificado", "baja", "dns", "dnf",
    "no", "presentado"  # para "No Presentado"
}

def clean_club_name_strict(raw: str) -> str:
    """
    Limpia nombre de club de forma estricta:
      - quita '(...)' final
      - elimina colas con tiempos/estados/puntos (p.ej. 'Descalificado 34', '00:30:25')
    """
    if not raw:
        return ""

    s = normalize_spaces(raw)

    # 1) quitar paréntesis final (categoría)
    s = re.sub(r"\s*\([^()]*\)\s*$", "", s).strip()

    # 2) limpiar tokens finales "basura"
    toks = s.split()

    # elimina desde el final: tiempos, estados, números (puntos), "No Presentado"
    while toks:
        t = toks[-1]
        tl = t.lower()

        if TIME_TOKEN_RE.fullmatch(t):
            toks.pop()
            continue

        if tl.isdigit():              # puntos u otros números sueltos al final
            toks.pop()
            continue

        if tl in STATUS_TOKENS:       # descalificado/baja/no/presentado
            toks.pop()
            continue

        # a veces aparece "No Presentado" como dos tokens, esto lo cubre el while
        break

    return " ".join(toks).strip()

def looks_like_club(name: str) -> bool:
    if not name or len(name) < 4:
        return False
    # si por alguna razón el "club" acaba siendo solo números/tiempos, lo descartamos
    if TIME_TOKEN_RE.fullmatch(name):
        return False
    if re.fullmatch(r"\d+", name):
        return False
    return True

def find_end_of_club(parts, start_idx):
    """
    Devuelve el índice donde termina el club (exclusivo).
    Club = parts[start_idx:end_idx]
    """
    for i in range(start_idx, len(parts)):
        t = parts[i]
        tl = t.lower()

        # si llega un tiempo, ahí empieza otra columna -> fin de club
        if TIME_TOKEN_RE.fullmatch(t):
            return i

        # si llega un estado, también fin de club
        if tl in STATUS_TOKENS:
            return i

        # a veces aparece puntuación suelta al final; si está muy al final,
        # puedes cortar también (opcional, más seguro al usar columnas)
    return len(parts)

def parse_individual_result_line(line: str):
    ln = normalize_spaces(line)
    parts = ln.split()
    if len(parts) < 6:
        return None
    if not parts[0].isdigit():
        return None

    pos = int(parts[0])

    # localizar año
    year_idx = None
    for i in range(1, min(len(parts), 20)):
        if re.fullmatch(r"\d{4}", parts[i]):
            year_idx = i
            break
    if year_idx is None:
        return None

    # localizar primer tiempo o estado hacia el final
    end_idx = None
    for i in range(len(parts)-1, year_idx, -1):
        if TIME_RE.fullmatch(parts[i]) or STATUS_RE.fullmatch(parts[i]):
            end_idx = i
            break
    if end_idx is None or end_idx <= year_idx + 1:
        # a veces hay varios tiempos; buscamos el primero desde year_idx
        for i in range(year_idx+1, len(parts)):
            if TIME_RE.fullmatch(parts[i]) or STATUS_RE.search(parts[i]):
                end_idx = i
                break
    if end_idx is None or end_idx <= year_idx + 1:
        return None

    
    club_start = year_idx + 1  # o club_start detectado
    club_end = find_end_of_club(parts, club_start)
    club_raw = " ".join(parts[club_start:club_end]).strip()
    club = clean_club_name_strict(club_raw)
    if not looks_like_club(club):
        return None  # o continue, según contexto
    club_id = f"club_{slugify(club)}"

    # atleta y birth_year (opcional para este paso)
    athlete_name = " ".join(parts[1:year_idx]).strip()
    birth_year = int(parts[year_idx])

    # tiempo/estado: tomamos el último tiempo encontrado en la línea (Final.T suele ir al final)
    times = TIME_RE.findall(ln)
    status = "OK"
    if STATUS_RE.search(ln):
        status = STATUS_RE.search(ln).group(1).upper()
    time_raw = times[-1] if times else ""

    return {
        "kind": "individual",
        "position": pos,
        "athlete_name": athlete_name,
        "birth_year": birth_year,
        "club": club,
        "time_raw": time_raw,
        "status": status,
    }

def find_club_start_index(parts, start=1):
    for i in range(start, len(parts)):
        tok = parts[i].lower()
        if tok in CLUB_START_TOKENS:
            return i
    return None

def parse_relay_result_start_line(line: str):
    ln = normalize_spaces(line)
    parts = ln.split()
    if len(parts) < 5:
        return None
    if not parts[0].isdigit():
        return None
    if not TIME_RE.search(ln) and not STATUS_RE.search(ln):
        return None

    pos = int(parts[0])

    # club empieza en token típico (Club / C.D. / etc.)
    club_start = find_club_start_index(parts, start=1)
    if club_start is None:
        return None

    # club termina justo antes del primer tiempo/estado
    end_idx = None
    for i in range(club_start+1, len(parts)):
        if TIME_RE.fullmatch(parts[i]) or STATUS_RE.search(parts[i]):
            end_idx = i
            break
    if end_idx is None:
        return None

    club_end = find_end_of_club(parts, club_start)
    club_raw = " ".join(parts[club_start:club_end]).strip()
    club = clean_club_name_strict(club_raw)
    if not looks_like_club(club):
        return None  # o continue, según contexto
    club_id = f"club_{slugify(club)}"
    
    # nombre(s) en la misma línea: tokens entre pos y club_start
    athlete_name = " ".join(parts[1:club_start]).strip()

    times = TIME_RE.findall(ln)
    status = "OK"
    if STATUS_RE.search(ln):
        status = STATUS_RE.search(ln).group(1).upper()
    time_raw = times[-1] if times else ""

    return {
        "kind": "relay",
        "position": pos,
        "club": club,
        "time_raw": time_raw,
        "status": status,
        "relay_athletes": [athlete_name] if athlete_name else []
    }

def is_relay_continuation_line(line: str) -> bool:
    ln = normalize_spaces(line)
    if not ln:
        return False
    # NO empieza por número (no es nuevo puesto)
    if re.match(r"^\d+\b", ln):
        return False
    # no contiene tiempo ni club (suele ser solo un nombre)
    if TIME_RE.search(ln) or "club" in ln.lower():
        return False
    # heurística: contiene coma (APELLIDO, NOMBRE) o muchas mayúsculas
    return ("," in ln) or (sum(1 for c in ln if c.isupper()) > 5)

def parse_results_and_clubs_from_pdf(pdf_path: str, competition_id: str, debug=False, club_filters=None):
    club_filters_norm = [normalize_key(x) for x in (club_filters or []) if x]

    clubs_map = {}   # club_id -> {id,name,slug}
    results = []

    def club_passes_filter(club_name: str) -> bool:
        if not club_filters_norm:
            return True
        ck = normalize_key(club_name)
        return any(f in ck for f in club_filters_norm)

    with pdfplumber.open(pdf_path) as pdf:
        current_relay = None

        for page_idx, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if not text:
                continue
            lines = [normalize_spaces(l) for l in text.split("\n") if l.strip()]

            for ln in lines:
                # 1) si estamos dentro de un relevo, mirar continuaciones
                if current_relay and is_relay_continuation_line(ln):
                    current_relay["relay_athletes"].append(normalize_spaces(ln))
                    continue

                # 2) intentar parsear individual
                ind = parse_individual_result_line(ln)
                if ind and ind.get("club"):
                    club_name = ind["club"]
                    if not club_passes_filter(club_name):
                        continue

                    club_id = f"club_{slugify(club_name)}"
                    clubs_map.setdefault(club_id, {"id": club_id, "name": club_name, "slug": slugify(club_name)})

                    rid = f"r_{competition_id}_{len(results)+1:06d}"
                    results.append({
                        "id": rid,
                        "competition_id": competition_id,
                        "club_id": club_id,
                        "kind": "individual",
                        "position": ind.get("position"),
                        "athlete_name": ind.get("athlete_name"),
                        "birth_year": ind.get("birth_year"),
                        "time_raw": ind.get("time_raw"),
                        "status": ind.get("status"),
                    })
                    current_relay = None
                    continue

                # 3) intentar parsear inicio de relevo
                rel = parse_relay_result_start_line(ln)
                if rel and rel.get("club"):
                    club_name = rel["club"]
                    if not club_passes_filter(club_name):
                        current_relay = None
                        continue

                    club_id = f"club_{slugify(club_name)}"
                    clubs_map.setdefault(club_id, {"id": club_id, "name": club_name, "slug": slugify(club_name)})

                    rid = f"r_{competition_id}_{len(results)+1:06d}"
                    row = {
                        "id": rid,
                        "competition_id": competition_id,
                        "club_id": club_id,
                        "kind": "relay",
                        "position": rel.get("position"),
                        "time_raw": rel.get("time_raw"),
                        "status": rel.get("status"),
                        "relay_athletes": rel.get("relay_athletes", [])
                    }
                    results.append(row)
                    current_relay = row
                    continue

                # si no matchea nada, cerramos relevo abierto
                current_relay = None

    if debug:
        print(f"DEBUG results en {os.path.basename(pdf_path)}: {len(results)}")
        print(f"DEBUG clubs en {os.path.basename(pdf_path)}: {len(clubs_map)}")

    return results, clubs_map

# ----------------------------
# DEPORTISTAS
# ----------------------------
def looks_like_row_start(ln: str) -> bool:
    return bool(re.match(r"^\d+\b", ln)) and (TIME_RE.search(ln) or STATUS_RE.search(ln))

def normalize_athlete_name(raw: str) -> str:
    """
    Normaliza 'APELLIDOS, NOMBRE' -> 'Nombre Apellidos'
    y aplica Title Case con conectores comunes en minúscula.
    """
    if not raw:
        return ""
    s = normalize_spaces(raw.replace("\u00a0", " "))

    # si viene con coma, invertimos
    if "," in s:
        a, b = [x.strip() for x in s.split(",", 1)]
        if a and b:
            s = f"{b} {a}".strip()

    # title case inteligente
    lower_words = {"de", "del", "la", "las", "los", "y", "e"}
    out = []
    for i, w in enumerate(s.split()):
        wl = w.lower()
        if i > 0 and wl in lower_words:
            out.append(wl)
        else:
            # conserva siglas tipo C.D.E
            if re.fullmatch(r"(?:[A-Za-z]\.){2,}", w):
                out.append(w.upper())
            else:
                out.append(wl.capitalize())
    return " ".join(out).strip()

def athlete_id(name: str, birth_year=None) -> str:
    by = str(birth_year) if birth_year else "na"
    return f"a_{slugify(name)}_{by}"

ATH_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")

def parse_individual_athlete_line(line: str):
    """
    Espera algo como: '1 APELLIDOS, NOMBRE 2003 Club ... 01:58:43 20'
    Devuelve (name, birth_year, club_name_clean) o None
    """
    ln = normalize_spaces(line)
    parts = ln.split()
    if len(parts) < 5:
        return None
    if not parts[0].isdigit():
        return None

    # localizar año
    yidx = None
    for i in range(1, min(len(parts), 25)):
        if re.fullmatch(r"(19\d{2}|20\d{2})", parts[i]):
            yidx = i
            break
    if yidx is None:
        return None

    # nombre = tokens entre pos y año
    raw_name = " ".join(parts[1:yidx]).strip()
    name = normalize_athlete_name(raw_name)
    if not name:
        return None

    birth_year = int(parts[yidx])

    # club_raw: tokens entre año y "fin de club" (tiempo/estado)
    club_start = yidx + 1
    club_end = find_end_of_club(parts, club_start)  
    club_raw = " ".join(parts[club_start:club_end]).strip()
    club_clean = clean_club_name_strict(club_raw)   
    if not looks_like_club(club_clean):
        # puede ser fila rara sin club o con columnas desplazadas
        return (name, birth_year, "")

    return (name, birth_year, club_clean)

def is_headerish_line(ln: str) -> bool:
    l = ln.lower()
    return any(k in l for k in HEADER_KEYWORDS)

def parse_relay_athlete_continuation(line: str):
    """
    Línea que contiene solo un nombre de deportista (sin pos, sin año, sin tiempos).
    Devuelve name o None.
    """
    ln = normalize_spaces(line)
    if not ln:
        return None
    if re.match(r"^\d+\b", ln):
        return None
    if ATH_YEAR_RE.search(ln) or TIME_RE.search(ln):
        return None
    if is_headerish_line(ln):
        return None
    if ln.count(",") != 1:
        return None
    if re.search(r"\d", ln):
        return None

    name = normalize_athlete_name(ln)
    return name if name else None

def parse_athletes_from_pdf(pdf_path: str, debug=False, club_filters=None):
    """
    Devuelve dict {athlete_id: {id,name,birth_year}} aplicando la regla:
      - Crear atletas CON año si existen en individuales.
      - Crear atletas SIN año SOLO si el nombre no aparece nunca con año (solo relays).
    Filtra por club (p.ej. Pacifico).
    """
    club_filters_norm = [normalize_key(x) for x in (club_filters or []) if x]

    def club_passes(club_name: str) -> bool:
        if not club_filters_norm:
            return True
        ck = normalize_key(club_name)
        return any(f in ck for f in club_filters_norm)

    # Evidencia
    seen_with_year = {}      # name_key -> set(years)
    display_name_by_key = {} # name_key -> display name normalizado (para emitir en dimensión)
    relay_names = set()      # name_key vistos en relays (solo nombres, sin año)

    current_relay_club = None  # club del relevo activo

    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if not text:
                continue
            lines = [normalize_spaces(l) for l in text.split("\n") if l.strip()]

            for ln in lines:                
                # Paso 1: cabecera => reset y skip
                if is_headerish_line(ln) or is_header_start(ln) or is_date_line(ln):
                    current_relay_club = None
                    continue

                #  Paso 2: inicio de nueva fila => reset del contexto de relevo (para evitar arrastres)
                if looks_like_row_start(ln):
                    # por defecto cerramos el relevo anterior
                    current_relay_club = None

                    # intentamos leer si esta fila es un relevo y capturar club
                    rel = parse_relay_result_start_line(ln)
                    if rel and rel.get("club") and club_passes(rel["club"]):
                        current_relay_club = rel["club"]
                        # añade el primer nombre si lo hay...
                                
                # 1) Individual: pos + "Apellidos, Nombre" + año + club...
                ind = parse_individual_athlete_line(ln)
                if ind:
                    name, by, club_clean = ind

                    # resetea contexto de relevo
                    current_relay_club = None

                    # Solo atletas del club filtrado
                    if club_clean and club_passes(club_clean):
                        key = athlete_key(name)
                        display_name_by_key.setdefault(key, name)
                        seen_with_year.setdefault(key, set()).add(by)

                        if debug:
                            print("DEBUG ATH IND:", name, by, "| club:", club_clean)
                    continue

                # 2) Inicio de relevo: pos + atleta1 + club + tiempo...
                rel = parse_relay_result_start_line(ln)
                if rel and rel.get("club"):
                    current_relay_club = rel["club"]  # nombre limpio del club

                    if current_relay_club and club_passes(current_relay_club):
                        first_names = rel.get("relay_athletes", [])
                        for nm in first_names:
                            nm_norm = normalize_athlete_name(nm)
                            if not nm_norm:
                                continue
                            key = athlete_key(nm_norm)
                            display_name_by_key.setdefault(key, nm_norm)
                            relay_names.add(key)

                            if debug:
                                print("DEBUG ATH RELAY START:", nm_norm, "| club:", current_relay_club)
                    continue

                # 3) Continuación de relevo: líneas con nombres sin pos/año/club
                if current_relay_club and club_passes(current_relay_club):
                    nm = parse_relay_athlete_continuation(ln)
                    if nm:
                        key = athlete_key(nm)
                        display_name_by_key.setdefault(key, nm)
                        relay_names.add(key)

                        if debug:
                            print("DEBUG ATH RELAY CONT:", nm, "| club:", current_relay_club)
                        continue

                # 4) Si no encaja, no tocamos el contexto (listas pueden continuar)
                #    (si quisieras, podrías resetear en cabeceras claras)

    # -------- Construcción final de la dimensión --------
    athletes = {}

    # A) Crear todos los atletas con año (si hay varios años, crea uno por año)
    for key, years in seen_with_year.items():
        name = display_name_by_key.get(key, key)
        for by in sorted(years):
            aid = athlete_id(name, by)
            athletes.setdefault(aid, {"id": aid, "name": name, "birth_year": by})

    # B) Crear atleta sin año SOLO si aparece en relay y NUNCA con año
    for key in relay_names:
        if key in seen_with_year:
            continue  # ya existe con año, no crear el "na"
        name = display_name_by_key.get(key, key)
        aid = athlete_id(name, None)
        athletes.setdefault(aid, {"id": aid, "name": name, "birth_year": None})

    if debug:
        print(f"DEBUG athletes final en {os.path.basename(pdf_path)}: {len(athletes)} "
              f"(with_year={sum(len(v) for v in seen_with_year.values())}, relay_only={len([k for k in relay_names if k not in seen_with_year])})")

    # Blindaje final: si existe atleta con año para ese nombre, elimina su versión "na"
    year_keys = set(seen_with_year.keys())
    to_delete = []
    for aid, obj in athletes.items():
        if obj.get("birth_year") is None:
            k = athlete_key(obj.get("name", ""))
            if k in year_keys:
                to_delete.append(aid)

    for aid in to_delete:
        athletes.pop(aid, None)

    if debug and to_delete:
        print("DEBUG removed relay-only duplicates:", len(to_delete))

    return athletes







# ----------------------------
# MAIN
# ----------------------------
def resolve_pdf_inputs(inputs, base_dir="./PDF", debug=False):
    """
    inputs: lista de strings que pueden ser:
      - nombre directo: "2026ddcc.pdf" o "2026ddcc"
      - patrón: "2025*" o "*.pdf" o "2025*.pdf"
    Devuelve lista de rutas completas dentro de base_dir.
    """
    resolved = []
    for raw in inputs:
        raw = raw.strip()

        # Si no tiene extensión pero tiene wildcard -> asumimos ".pdf"
        if ("*" in raw or "?" in raw) and not raw.lower().endswith(".pdf"):
            pattern = raw + ".pdf"
        # Si no tiene wildcard y no tiene extensión -> añadimos ".pdf"
        elif ("*" not in raw and "?" not in raw) and not raw.lower().endswith(".pdf"):
            pattern = raw + ".pdf"
        else:
            pattern = raw

        full_pattern = os.path.join(base_dir, pattern)
        matches = glob(full_pattern)

        if debug:
            print(f"DEBUG resolve pattern: {raw} -> {full_pattern} -> {len(matches)} matches")

        resolved.extend(matches)

    # dedup + sort
    resolved = sorted(set(resolved))
    return resolved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "pdf_inputs",
        nargs="*",
        help="PDF(s) o patrones. Ej: 2026ddcc.pdf | 2025* | *.pdf"
    )
    parser.add_argument("--debug", action="store_true")
    parser.add_argument(
        "--output",
        default="./JSON/pdf2jsontree.json",
        help="Ruta de salida JSON (por defecto ./JSON/pdf2jsontree.json)"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Si un PDF falla (p.ej. no encuentra fecha), detiene el proceso."
    )
    parser.add_argument(
        "--club-filter",
        action="append",
        default=None,
        help="Filtra clubes por subcadena (repetible). Ej: --club-filter Pacifico"
    )

    args = parser.parse_args()

    os.makedirs("./PDF", exist_ok=True)
    os.makedirs("./JSON", exist_ok=True)

    # Si no pasan inputs, por defecto procesamos todos los PDFs
    inputs = args.pdf_inputs if args.pdf_inputs else ["*.pdf"]
    pdf_files = resolve_pdf_inputs(inputs, base_dir="./PDF", debug=args.debug)

    if not pdf_files:
        raise SystemExit("No se encontraron PDFs con los patrones indicados en ./PDF")

    # Acumuladores (para un único JSON final)
    competitions = []
    seasons_map = {}  # id -> {"id":..., "label":...}

    processed = []
    skipped = []

    clubs_map_global = {}  # club_id -> obj
    results_global = []

    athletes_map_global = {}  # athlete_id -> obj


    # El Loop de procesamiento principal: iterar sobre PDFs, extraer datos, acumular en estructuras globales
    for pdf_path in pdf_files:
        try:
            if args.debug:
                print("\n========================================")
                print("DEBUG procesando:", os.path.basename(pdf_path))
                print("========================================")

            with pdfplumber.open(pdf_path) as pdf:
                header_lines = extract_header_lines(pdf, debug=args.debug)
                competition = parse_competition_from_header(header_lines, debug=args.debug)
                season = parse_season_from_header(header_lines, competition=competition, debug=args.debug)

            # Añadir season
            seasons_map[season["id"]] = {"id": season["id"], "label": season["label"]}

            # Añadir competition (id provisional: c_XXX)
            comp_id = f"c_{len(competitions)+1:03d}"
            competitions.append({
                "id": comp_id,
                "season_id": season["id"],
                "name": competition["name"],
                "date": competition["date"],
                "date_start": competition["date_start"],
                "date_end": competition["date_end"],
                "location": competition["location"],
                "region": competition["region"],
                "pool_type": competition["pool_type"],
                "source_file": os.path.basename(pdf_path)
            })

            # ---- results + clubs
            res, clubs_map = parse_results_and_clubs_from_pdf(
                pdf_path,
                competition_id=comp_id,
                debug=args.debug,
                club_filters=args.club_filter
            )
            for cid, cobj in clubs_map.items():
                clubs_map_global.setdefault(cid, cobj)
            results_global.extend(res)

            processed.append(os.path.basename(pdf_path))

            ath_map = parse_athletes_from_pdf(
                pdf_path,
                debug=args.debug,
                club_filters=args.club_filter  # Pacífico
            )
            for aid, aobj in ath_map.items():
                athletes_map_global.setdefault(aid, aobj)

        except Exception as e:
            msg = f"{os.path.basename(pdf_path)} -> {e}"
            if args.debug:
                print("DEBUG ERROR:", msg)
        
            # seguir SIEMPRE (modo lote)
            skipped.append({"file": os.path.basename(pdf_path), "reason": str(e)})
            continue

    # ---- Consolidación global de athletes ----
    # Regla: si existe atleta con año para ese nombre (en cualquier PDF),
    # eliminar su versión "_na" creada en PDFs anteriores.
    name_has_year = set()
    to_delete = []

    for aid, aobj in athletes_map_global.items():
        if aobj.get("birth_year") is not None:
            k = athlete_key(aobj.get("name", ""))
            if k:
                name_has_year.add(k)

    for aid, aobj in list(athletes_map_global.items()):
        if aobj.get("birth_year") is None:
            k = athlete_key(aobj.get("name", ""))
            if k in name_has_year:
                to_delete.append(aid)
                athletes_map_global.pop(aid, None)

    if args.debug and to_delete:
        print("DEBUG athletes global: removed _na duplicates:", len(to_delete))


    # ---- Construcción del JSON ----
    data = {
        "meta": {
            "version": "1.0.0",
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "timezone": "Europe/Madrid",
            "source": {
                "generator": "pdf2tree.py",
                "inputs": inputs,
                "inputs_resolved": processed,
                "skipped": skipped
            }
        },
        "dimensions": {
            "seasons": list(seasons_map.values()),
            "clubs": list(clubs_map_global.values()),
            "athletes": list(athletes_map_global.values()),
            "competitions": competitions
        },
        "results": results_global
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    if args.debug:
        print(f"\nDEBUG JSON generado en {args.output}")
        print("DEBUG procesados:", len(processed), "omitidos:", len(skipped))

if __name__ == "__main__":
    main()