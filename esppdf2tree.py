#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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

# ----------------------------
# Fechas
# ----------------------------
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

RANGE_RE = re.compile(
    r"(?P<d1>\d{1,2})\s*(?:-|al|a)\s*(?P<d2>\d{1,2})\s+de\s+(?P<m>[a-záéíóúñ]+)\s+(?P<y>\d{4})",
    re.IGNORECASE
)


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

            processed.append(os.path.basename(pdf_path))

        except Exception as e:
            msg = f"{os.path.basename(pdf_path)} -> {e}"
            if args.debug:
                print("DEBUG ERROR:", msg)
        
            # seguir SIEMPRE (modo lote)
            skipped.append({"file": os.path.basename(pdf_path), "reason": str(e)})
            continue

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
            "competitions": competitions
        }
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    if args.debug:
        print(f"\nDEBUG JSON generado en {args.output}")
        print("DEBUG procesados:", len(processed), "omitidos:", len(skipped))

if __name__ == "__main__":
    main()