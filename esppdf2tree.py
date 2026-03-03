#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
import argparse
import unicodedata
from datetime import datetime
import pdfplumber

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
    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
    "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
    "septiembre": "09", "setiembre": "09",
    "octubre": "10", "noviembre": "11", "diciembre": "12"
}

DATE_RE = re.compile(
    r"(?P<d1>\d{1,2})\s*(?:de)?\s*(?P<m>[a-záéíóúñ]+)\s*(?:de)?\s*(?P<y>\d{4})",
    re.IGNORECASE
)

RANGE_RE = re.compile(
    r"(?P<d1>\d{1,2})\s*(?:-|al|a)\s*(?P<d2>\d{1,2})\s+de\s+(?P<m>[a-záéíóúñ]+)\s+(?P<y>\d{4})",
    re.IGNORECASE
)

def parse_dates(text: str, debug=False):
    text = normalize_dashes(text.lower().strip())

    # Caso 1: rango con dos fechas completas (15 noviembre 2025 - 16 noviembre 2025)
    if " - " in text:
        left, right = [t.strip() for t in text.split(" - ", 1)]

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

                if debug:
                    print("DEBUG fechas rango completo:", date_start, date_end)

                return date_start, date_end

    # Caso 2: rango compacto (15-16 noviembre 2025)
    m_range = RANGE_RE.search(text)
    if m_range:
        mm = MONTHS_ES.get(strip_accents(m_range.group("m")), "")
        y = m_range.group("y")
        d1 = int(m_range.group("d1"))
        d2 = int(m_range.group("d2"))

        if mm:
            return (
                f"{y}-{mm}-{d1:02d}",
                f"{y}-{mm}-{d2:02d}"
            )

    # Caso 3: fecha única
    m_single = DATE_RE.search(text)
    if m_single:
        mm = MONTHS_ES.get(strip_accents(m_single.group("m")), "")
        y = m_single.group("y")
        d = int(m_single.group("d1"))

        if mm:
            return f"{y}-{mm}-{d:02d}", None

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

def extract_header_lines(pdf, debug=False):
    for page in pdf.pages:
        text = page.extract_text()
        if not text:
            continue

        lines = [normalize_spaces(l) for l in text.split("\n") if l.strip()]

        for i, ln in enumerate(lines):
            if ln.upper().startswith("RESULTADOS"):
                # coger desde "Resultados" hasta la primera línea que contenga fecha
                header = []
                for j in range(i, len(lines)):
                    header.append(lines[j])
                    if DATE_RE.search(lines[j].lower()):
                        if debug:
                            print("DEBUG cabecera real detectada:")
                            for x in header:
                                print(" ", x)
                        return header

                # fallback: si no encuentro fecha, devuelvo unas pocas líneas
                if debug:
                    print("DEBUG cabecera (sin fecha detectada, fallback):")
                    for x in lines[i:i+8]:
                        print(" ", x)
                return lines[i:i+8]

    return []

def parse_competition_from_header(lines, debug=False):
    name_lines = []
    location = ""
    region = ""
    pool_type = ""
    date_start = None
    date_end = None

    # buscamos la línea que contiene la fecha
    date_idx = None
    for i, ln in enumerate(lines):
        if DATE_RE.search(ln.lower()) or RANGE_RE.search(ln.lower()):
            date_idx = i
            break

    if date_idx is None:
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

    # localización = línea inmediatamente anterior
    if date_idx - 1 >= 0:
        loc = lines[date_idx - 1]
        if "," in loc:
            location, region = [normalize_title(x.strip()) for x in loc.split(",", 1)]
        else:
            location = normalize_title(loc)

    # nombre = desde la línea 1 hasta antes de la localización
    name_lines = lines[1:date_idx - 1]
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

# ----------------------------
# MAIN
# ----------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    os.makedirs("./PDF", exist_ok=True)
    os.makedirs("./JSON", exist_ok=True)

    pdf_path = "./PDF/2026ddcc.pdf"
    out_path = "./JSON/pdf2jsontree.json"

    with pdfplumber.open(pdf_path) as pdf:
        header_lines = extract_header_lines(pdf, debug=args.debug)
        competition = parse_competition_from_header(header_lines, debug=args.debug)
        season = parse_season_from_header(header_lines, competition=competition, debug=args.debug)

    data = {
        "meta": {
            "version": "1.0.0",
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "timezone": "Europe/Madrid",
            "source": {
                "file": os.path.basename(pdf_path),
                "generator": "pdf2tree.py"
            }
        },
        "dimensions": {
            "seasons": [
                {
                    "id": season["id"],
                    "label": season["label"],
                }
            ],
            "competitions": [
                {
                    "id": "c_001",
                    "name": competition["name"],
                    "date": competition["date"],
                    "date_start": competition["date_start"],
                    "date_end": competition["date_end"],
                    "location": competition["location"],
                    "region": competition["region"],
                    "pool_type": competition["pool_type"]
                }
            ]
        }
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    if args.debug:
        print(f"DEBUG JSON generado en {out_path}")

if __name__ == "__main__":
    main()