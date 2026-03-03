#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
import argparse
import unicodedata
import html
import sys
import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from glob import glob

import pdfplumber

# ----------------------------
# Utilidades
# ----------------------------

def normalize_text(s: str) -> str:
    """Quita tildes y pasa a minúsculas (para comparaciones/slug)."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()

def slugify(s: str) -> str:
    s = normalize_text(s)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "na"

def ensure_dirs():
    os.makedirs("./PDF", exist_ok=True)
    os.makedirs("./JSON", exist_ok=True)

def normalize_athlete_name(raw: str) -> str:
    """
    - limpia espacios
    - convierte 'APELLIDOS, NOMBRE' -> 'Nombre Apellidos'
    - Title Case inteligente con conectores en minúscula
    """
    if not raw:
        return ""
    s = raw.replace("\u00a0", " ").strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s*,\s*", ", ", s)

    if "," in s:
        parts = [p.strip() for p in s.split(",", 1)]
        if len(parts) == 2 and parts[0] and parts[1]:
            s = f"{parts[1]} {parts[0]}".strip()

    lower_words = {
        "de", "del", "la", "las", "los", "y", "e",
        "da", "do", "dos", "das", "san", "santa",
        "von", "van", "di", "du"
    }

    tokens = s.split(" ")
    out = []
    for i, t in enumerate(tokens):
        if not t:
            continue
        if re.fullmatch(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]\.", t):
            out.append(t.upper())
            continue
        tl = t.lower()
        if i > 0 and tl in lower_words:
            out.append(tl)
        else:
            out.append(tl.title())
    return " ".join(out).strip()

# Guiones comunes: hyphen, en-dash, em-dash, minus, etc.
DASH_CHARS_CLASS = r"[-‐‑‒–—−]"

def limpiar_competicion(nombre: str) -> str:
    """
    Limpia el nombre de competición para mostrar:
    - Quita 'Fase Territorial' (case-insensitive)
    - Normaliza guiones raros
    - Compacta espacios
    """
    if not nombre:
        return ""
    s = str(nombre).strip()

    # 1) Quitar 'Fase Territorial' aunque venga rodeado de guiones/espacios
    #    Ej: " - Fase Territorial - " / "– FASE TERRITORIAL –" / "FASE TERRITORIAL"
    s = re.sub(
        rf"(\s*{DASH_CHARS_CLASS}\s*)?\bfase\s+territorial\b(\s*{DASH_CHARS_CLASS}\s*)?",
        " ",
        s,
        flags=re.IGNORECASE
    )

    # 2) Normalizar cualquier guion a " – " (opcional: si prefieres, a " - ")
    s = re.sub(rf"\s*{DASH_CHARS_CLASS}\s*", " – ", s)

    # 3) Quitar dobles separadores (por si quedaron)
    s = re.sub(r"(?:\s*–\s*){2,}", " – ", s)

    # 4) Compactar espacios
    s = re.sub(r"\s+", " ", s).strip()

    # 5) Si queda un separador al inicio/fin, quítalo
    s = re.sub(r"^–\s*", "", s).strip()
    s = re.sub(r"\s*–$", "", s).strip()

    return s

# ----------------------------
# Reconstrucción de líneas
# ----------------------------

def extract_lines(page: pdfplumber.page.Page, y_tol: float = 2.0) -> List[str]:
    words = page.extract_words(
        x_tolerance=2,
        y_tolerance=2,
        keep_blank_chars=False,
        use_text_flow=True
    )
    words.sort(key=lambda w: (w["top"], w["x0"]))

    lines = []
    current_words = []
    current_top = None

    for w in words:
        if current_top is None or abs(w["top"] - current_top) <= y_tol:
            current_words.append(w["text"])
            current_top = w["top"] if current_top is None else (current_top + w["top"]) / 2
        else:
            lines.append(" ".join(current_words).strip())
            current_words = [w["text"]]
            current_top = w["top"]

    if current_words:
        lines.append(" ".join(current_words).strip())

    lines = [re.sub(r"\s+", " ", ln).strip() for ln in lines if ln.strip()]
    return lines

def extract_header_lines(page: pdfplumber.page.Page, max_lines: int = 12) -> List[str]:
    return extract_lines(page)[:max_lines]

def clean_line_for_matching(line: str) -> str:
    line = line.replace("\u00a0", " ").strip()
    line = re.sub(r"^[\*•·]+", "", line).strip()
    return line

# ----------------------------
# Cabecera: competición / fecha / temporada
# ----------------------------

MONTHS_ES = {
    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
    "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
    "septiembre": "09", "setiembre": "09", "octubre": "10",
    "noviembre": "11", "diciembre": "12",
}

DATE_RE = re.compile(
    r"(?P<day>\d{1,2}(?:-\d{1,2})?)\s+de\s+(?P<month>[A-Za-zÁÉÍÓÚÑáéíóúñ]+)\s+(?P<year>\d{4})",
    re.IGNORECASE
)

DASH_CHARS = DASH_CHARS_CLASS

def normalize_header_separators(s: str) -> str:
    s = html.unescape(s)
    s = s.replace("\u00a0", " ").strip()
    s = re.sub(r"\s+", " ", s)
    # Caso típico de separador extraído como "3" entre tokens
    s = re.sub(r"(?<=\S)\s3\s(?=\S)", " – ", s)
    s = re.sub(rf"\s*{DASH_CHARS}\s*", " – ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def spanish_date_to_ddmmyyyy(text: str) -> str:
    m = DATE_RE.search(text)
    if not m:
        return ""
    day = m.group("day").split("-")[0]
    month = normalize_text(m.group("month"))
    year = m.group("year")
    mm = MONTHS_ES.get(month, "")
    if not mm:
        return ""
    return f"{int(day):02d}/{mm}/{year}"

def ddmmyyyy_to_iso(ddmmyyyy: str) -> str:
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", ddmmyyyy.strip())
    if not m:
        return ""
    dd, mm, yyyy = m.groups()
    return f"{yyyy}-{mm}-{dd}"

def season_end_year_from_date_iso(date_iso: str) -> Optional[int]:
    """
    Regla de temporada:
    - Si la fecha está en octubre, noviembre o diciembre => temporada = año+1
    - Si está en enero..septiembre => temporada = año
    """
    if not date_iso:
        return None
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", date_iso.strip())
    if not m:
        return None
    yyyy, mm, dd = map(int, m.groups())
    return yyyy + 1 if mm >= 10 else yyyy

def season_label_from_end_year(end_year: int) -> str:
    start_year = end_year - 1
    return f"Temporada {start_year}-{end_year}"

def infer_season_from_text(text: str) -> str:
    m = re.search(r"\b(\d{2})\s*-\s*(\d{2})\b", text)
    if m:
        a, b = m.groups()
        return f"Temporada 20{a}-20{b}"
    m = re.search(r"\b(20\d{2})\s*-\s*(20\d{2})\b", text)
    if m:
        a, b = m.groups()
        return f"Temporada {a}-{b}"
    return "Temporada (desconocida)"

def extract_competition_details(pdf: pdfplumber.PDF, debug: bool = False) -> Tuple[str, Dict[str, str], str]:
    """
    - Busca "RESULTADOS DEFINITIVOS" y toma:
      * línea siguiente como nombre competición
      * siguiente como línea de fecha/lugar
    - Infere temporada en base a portada/cabecera
    """
    header_lines = None
    for i in range(1, len(pdf.pages)) if len(pdf.pages) > 1 else range(0, len(pdf.pages)):
        lines = [clean_line_for_matching(l) for l in extract_header_lines(pdf.pages[i], max_lines=12)]
        if any("RESULTADOS DEFINITIVOS" in ln.upper() for ln in lines):
            header_lines = lines
            break

    if header_lines is None:
        header_lines = [clean_line_for_matching(l) for l in extract_header_lines(pdf.pages[0], max_lines=12)]

    if debug:
        print("DEBUG header_lines:")
        for idx, ln in enumerate(header_lines):
            print(f"  {idx}: {ln}")

    idx_res = next((k for k, ln in enumerate(header_lines) if "RESULTADOS DEFINITIVOS" in ln.upper()), None)

    competition_name = ""
    info_line = ""

    if idx_res is not None:
        if idx_res + 1 < len(header_lines):
            competition_name = normalize_header_separators(header_lines[idx_res + 1])
        if idx_res + 2 < len(header_lines):
            info_line = normalize_header_separators(header_lines[idx_res + 2])

        if info_line and not DATE_RE.search(info_line) and idx_res + 3 < len(header_lines):
            merged = f"{info_line} – {header_lines[idx_res + 3]}"
            if DATE_RE.search(merged):
                info_line = normalize_header_separators(merged)

    fecha = spanish_date_to_ddmmyyyy(info_line)

    lugar = ""
    mdate = DATE_RE.search(info_line)
    if mdate:
        tail = info_line[mdate.end():].strip()
        tail = re.sub(rf"^(?:\s*{DASH_CHARS}\s*)+", "", tail)
        parts = [p.strip() for p in re.split(rf"\s*{DASH_CHARS}\s*", tail) if p.strip()]
        if parts:
            lugar = parts[0]

    details = {
        "Fecha Competición": fecha,
        "Lugar Competición": lugar,
        "Comunidad Competición": "Madrid",
        "Tipo Piscina": ""
    }

    cover_lines = extract_header_lines(pdf.pages[0], max_lines=20)
    season = infer_season_from_text(" ".join(cover_lines) + " " + " ".join(header_lines))

    if debug:
        print("DEBUG competition_name:", competition_name)
        print("DEBUG info_line:", info_line)
        print("DEBUG details:", details)
        print("DEBUG season:", season)

    return competition_name, details, season

# ----------------------------
# Parsing de eventos / participantes
# ----------------------------

# Evento: soporta cualquier distancia 2-3 dígitos (50, 100, 200, etc.).
# Evita relevos tipo "4x50" (no empieza por dígitos puros).
EVENT_RE = re.compile(r"^(?:\d{2,3})\s*m\.?\s+", re.IGNORECASE)

# Dejamos el regex original como fallback por si algún PDF raro no se tokeniza bien.
ATHLETE_RE = re.compile(
    r"^(?P<pos>\d{1,3})\s+"
    r"(?P<name>.+?)\s+"
    r"(?P<year>\d{4})\s+"
    r"(?P<club>.+?)\s+"
    r"(?P<time>(?:\d{1,2}:\d{2}:\d{2}|Descalificado))\s*"
    r"(?P<points>\d+)?\s*$",
    re.IGNORECASE
)

TIME_TOKEN_RE = re.compile(r"^\d{1,2}:\d{2}:\d{2}$", re.IGNORECASE)

def parse_athlete_line(line_clean: str) -> Optional[Dict]:
    """
    Parser robusto por tokens:
    Espera: <pos> <nombre...> <año> <club...> <tiempo|Descalificado> [puntos?]
    Devuelve dict o None si no parece línea de atleta.
    """
    parts = line_clean.split()
    if len(parts) < 6:
        return None

    if not parts[0].isdigit():
        return None
    pos = int(parts[0])

    year_idx = None
    for i in range(1, min(len(parts), 12)):
        if re.fullmatch(r"\d{4}", parts[i]):
            year_idx = i
            break
    if year_idx is None:
        return None
    year = int(parts[year_idx])

    time_idx = None
    time_token = None
    for i in range(len(parts) - 1, year_idx, -1):
        token = parts[i]
        if TIME_TOKEN_RE.fullmatch(token) or token.lower().startswith("descal"):
            time_idx = i
            time_token = token
            break
    if time_idx is None:
        return None

    points = None
    if time_idx + 1 < len(parts) and parts[time_idx + 1].isdigit():
        points = int(parts[time_idx + 1])
    elif parts[-1].isdigit() and parts[-1] != parts[0]:
        points = int(parts[-1])

    name = " ".join(parts[1:year_idx]).strip()
    club = " ".join(parts[year_idx + 1:time_idx]).strip()

    if not name or not club:
        return None

    return {"pos": pos, "name": name, "year": year, "club": club, "time": time_token, "points": points}

def is_footer_or_noise(line: str) -> bool:
    upper = line.upper()
    if "FEDERACIÓN" in upper and "SALVAMENTO" in upper:
        return True
    if "FMSS.ES" in upper or "SOSMADRID" in upper:
        return True
    if line.startswith("T.") or line.startswith("Fax"):
        return True
    if line.startswith("Socorrista / Lifeguard"):
        return True
    if upper.startswith("RESULTADOS DEFINITIVOS"):
        return True
    return False

def parse_sex_from_event(event_line: str) -> str:
    s = event_line.strip()
    if re.search(r"\bMasculin[oa]\b", s, re.IGNORECASE) or re.search(r"\bM$", s):
        return "M"
    if re.search(r"\bFemenin[oa]\b", s, re.IGNORECASE) or re.search(r"\bF$", s):
        return "F"
    if re.search(r"\bMixto\b", s, re.IGNORECASE):
        return "X"
    return ""

MASTER_CAT_RE = re.compile(
    r"\b(Máster|Master)\b"
    r"(?:\s+(?P<range>\d{2}\s*-\s*\d{2}))?"
    r"(?:\s+(?P<plus>\+\s*\d{2}|\d{2}\s*\+))?",
    re.IGNORECASE
)

def parse_category_from_event(event_line: str) -> str:
    # 1) Máster con rango o +edad
    m = MASTER_CAT_RE.search(event_line)
    if m:
        base = "Máster"
        r = m.group("range")
        p = m.group("plus")
        if r:
            r_norm = re.sub(r"\s*", "", r)  # "60 - 69" -> "60-69"
            return f"{base} {r_norm}"
        if p:
            num = re.search(r"(\d{2})", p).group(1)
            return f"{base} +{num}"
        return base

    # 2) Otras categorías
    for cat in ["Absoluto", "Junior", "Juvenil", "Cadete"]:
        if re.search(r"\b" + re.escape(cat) + r"\b", event_line, re.IGNORECASE):
            return cat

    return ""

SEX_WORDS_RE = re.compile(r"\b(Femenin[oa]|Masculin[oa]|Mixto)\b", re.IGNORECASE)
SHORT_SEX_RE = re.compile(r"\s+[MF]$", re.IGNORECASE)

def parse_prueba_from_event(event_line: str) -> str:
    s = re.sub(r"\s+", " ", event_line).strip()
    s = SEX_WORDS_RE.sub("", s).strip()
    s = SHORT_SEX_RE.sub("", s).strip()

    m_master = re.search(r"\b(Máster|Master)\b", s, re.IGNORECASE)
    if m_master:
        return s[:m_master.start()].strip()

    m = re.search(r"\b(Cadete|Juvenil|Junior|Absoluto)\b", s, re.IGNORECASE)
    if m:
        return s[:m.start()].strip()

    return s

def master_band_key(category: str) -> int:
    if not category:
        return 9999
    m = re.search(r"(\d{2})\s*-\s*\d{2}", category)
    if m:
        return int(m.group(1))
    m = re.search(r"\+(\d{2})", category)
    if m:
        return int(m.group(1))
    return 0

def convert_time_mmsscc_to_mmssmmm(t: str) -> str:
    """Convierte mm:ss:cc -> mm:ss.mmm (cc=centésimas -> ms)."""
    m = re.match(r"^(\d+):(\d{2}):(\d{2})$", t.strip())
    if not m:
        return ""
    mm, ss, cc = map(int, m.groups())
    ms = cc * 10
    return f"{mm:02d}:{ss:02d}.{ms:03d}"

def mmssmmm_to_seconds(t: str) -> Optional[float]:
    """Convierte mm:ss.mmm -> segundos float."""
    if not t:
        return None
    m = re.match(r"^(\d+):(\d{2})\.(\d{3})$", t.strip())
    if not m:
        return None
    mm, ss, mmm = map(int, m.groups())
    return mm * 60 + ss + (mmm / 1000.0)

@dataclass
class ParticipantRow:
    athlete_name: str
    birth_year: int
    sex: str
    club: str
    prueba_base: str
    category: str
    grouping: str
    position: Optional[int]
    points: Optional[int]
    status: str  # OK / DSQ
    time_raw: str
    time_display: str
    time_seconds: Optional[float]

def parse_participants_all_clubs(pdf: pdfplumber.PDF, debug: bool = False) -> List[ParticipantRow]:
    participants: List[ParticipantRow] = []
    current_event = None
    current_sex = ""
    current_category = ""
    current_prueba = ""

    for page_idx, page in enumerate(pdf.pages[1:], start=2):
        for line in extract_lines(page):
            if is_footer_or_noise(line):
                continue

            line_clean = clean_line_for_matching(line)

            # Detectar evento
            if EVENT_RE.match(line_clean):
                current_event = line_clean
                current_sex = parse_sex_from_event(current_event)
                current_category = parse_category_from_event(current_event)
                current_prueba = parse_prueba_from_event(current_event)
                if debug:
                    print(f"DEBUG event (p{page_idx}): {current_event}")
                continue

            if not current_event:
                continue

            # DEBUG: imprimir líneas "raw" candidatas a atleta
            if debug and ("Descalificado" in line_clean or re.search(r"\b\d{1,2}:\d{2}:\d{2}\b", line_clean)):
                print(f"DEBUG raw_line (p{page_idx}): {line_clean}")

            # 1) Intento robusto tokenizado
            parsed = parse_athlete_line(line_clean)

            # 2) Fallback al regex si tokenizado falla
            if not parsed:
                m = ATHLETE_RE.match(line_clean)
                if not m:
                    continue
                gd = m.groupdict()
                parsed = {
                    "pos": int(gd["pos"]) if gd.get("pos") else None,
                    "name": gd["name"],
                    "year": int(gd["year"]),
                    "club": gd["club"],
                    "time": gd["time"],
                    "points": int(gd["points"]) if gd.get("points") else None
                }

            raw_time = (parsed["time"] or "").strip()
            club = (parsed["club"] or "").strip()

            status = "OK"
            time_display = ""
            time_seconds = None

            if raw_time.lower().startswith("descal"):
                status = "DSQ"
                time_display = "DSQ"
                time_seconds = None
            else:
                time_display = convert_time_mmsscc_to_mmssmmm(raw_time)
                time_seconds = mmssmmm_to_seconds(time_display)

            participants.append(
                ParticipantRow(
                    athlete_name=normalize_athlete_name(parsed["name"]),
                    birth_year=int(parsed["year"]),
                    sex=current_sex,
                    club=club,
                    prueba_base=current_prueba,
                    category=current_category,
                    grouping=current_event,
                    position=parsed.get("pos"),
                    points=parsed.get("points"),
                    status=status,
                    time_raw=raw_time,
                    time_display=time_display if time_display else ("DSQ" if status == "DSQ" else ""),
                    time_seconds=time_seconds
                )
            )

            if debug:
                print(f"DEBUG athlete (p{page_idx}): {participants[-1]}")

    return participants

# ----------------------------
# Construcción del árbol + dimensiones
# ----------------------------

def build_ids(
    season_label: str, competition_name: str, date_iso: str, location: str,
    prueba_base: str, category: str, sex: str,
    athlete_name: str, birth_year: int, club: str
) -> Dict[str, str]:
    season_id = f"s_{slugify(season_label.replace('Temporada', '').strip())}"
    competition_name_clean = limpiar_competicion(competition_name)
    loc = location or ""
    comp_key = f"{date_iso}_{loc}_{competition_name_clean}"
    competition_id = f"c_{slugify(comp_key)}"
    event_id = f"e_{slugify(prueba_base)}_{slugify(category)}_{(sex.lower() if sex else 'u')}"
    athlete_id = f"a_{slugify(athlete_name)}_{birth_year}"
    club_id = f"club_{slugify(club)}"
    return {
        "season_id": season_id,
        "competition_id": competition_id,
        "event_id": event_id,
        "athlete_id": athlete_id,
        "club_id": club_id
    }

def build_tree_json(pdf_path: str, debug: bool = False, club_filters: Optional[List[str]] = None) -> Dict:
    with pdfplumber.open(pdf_path) as pdf:
        competition_name, details, season_label = extract_competition_details(pdf, debug=debug)
        participants = parse_participants_all_clubs(pdf, debug=debug)

    date_iso = ddmmyyyy_to_iso(details.get("Fecha Competición", ""))

    # Temporada derivada de la fecha (regla Oct–Sep)
    end_year = season_end_year_from_date_iso(date_iso)
    if end_year:
        season_label = season_label_from_end_year(end_year)

    location = details.get("Lugar Competición", "")
    region = details.get("Comunidad Competición", "")
    pool_type = details.get("Tipo Piscina", "")

    if club_filters:
        norm_filters = [normalize_text(c) for c in club_filters]
        participants = [p for p in participants if any(f in normalize_text(p.club) for f in norm_filters)]

    dims = {"seasons": {}, "clubs": {}, "athletes": {}, "competitions": {}, "events": {}}

    season_id = f"s_{slugify(season_label.replace('Temporada', '').strip())}"
    dims["seasons"][season_id] = {"id": season_id, "label": season_label}

    competition_name_clean = limpiar_competicion(competition_name)
    loc = location or ""
    competition_id = f"c_{slugify(f'{date_iso}_{loc}_{competition_name_clean}')}"
    dims["competitions"][competition_id] = {
        "id": competition_id,
        "season_id": season_id,
        "date": date_iso,
        "name": competition_name,
        "name_clean": competition_name_clean,
        "location": location,
        "region": region,
        "pool_type": pool_type
    }

    events_map: Dict[str, Dict] = {}
    results_flat = []

    for p in participants:
        ids = build_ids(
            season_label=season_label,
            competition_name=competition_name,
            date_iso=date_iso,
            location=location,
            prueba_base=p.prueba_base,
            category=p.category,
            sex=p.sex,
            athlete_name=p.athlete_name,
            birth_year=p.birth_year,
            club=p.club
        )

        if ids["club_id"] not in dims["clubs"]:
            dims["clubs"][ids["club_id"]] = {"id": ids["club_id"], "name": p.club, "slug": slugify(p.club)}

        if ids["athlete_id"] not in dims["athletes"]:
            dims["athletes"][ids["athlete_id"]] = {"id": ids["athlete_id"], "name": p.athlete_name, "birth_year": p.birth_year}

        if ids["event_id"] not in dims["events"]:
            dist = None
            m = re.match(r"^(\d+)\s*m", p.prueba_base, re.IGNORECASE)
            if m:
                dist = int(m.group(1))
            dims["events"][ids["event_id"]] = {
                "id": ids["event_id"],
                "base": p.prueba_base,
                "sex": p.sex,
                "category": p.category,
                "distance_m": dist,
                "discipline": p.prueba_base
            }

        if ids["event_id"] not in events_map:
            events_map[ids["event_id"]] = {
                "event_id": ids["event_id"],
                "base": p.prueba_base,
                "sex": p.sex,
                "category": p.category,
                "athletes": []
            }

        athlete_node = {
            "athlete_id": ids["athlete_id"],
            "club_id": ids["club_id"],
            "status": p.status,
            "position": p.position,
            "points": p.points,
            "time": {"display": p.time_display, "seconds": p.time_seconds, "raw": p.time_raw}
        }
        events_map[ids["event_id"]]["athletes"].append(athlete_node)

        # res_id sin saltos de línea (estable)
        res_key = f"{date_iso}|{competition_id}|{ids['event_id']}|{ids['athlete_id']}"
        res_id = f"r_{slugify(res_key)}"

        results_flat.append({
            "id": res_id,
            "date": date_iso,
            "season_id": season_id,
            "competition_id": competition_id,
            "event_id": ids["event_id"],
            "athlete_id": ids["athlete_id"],
            "club_id": ids["club_id"],
            "time": {"display": p.time_display, "seconds": p.time_seconds, "raw": p.time_raw},
            "status": p.status,
            "position": p.position,
            "points": p.points,
            "labels": {"x": f"{date_iso}\n{competition_name}"}
        })

    # Orden deportistas dentro de cada evento: OK por tiempo, DSQ al final
    for ev in events_map.values():
        def sort_key(a):
            sec = a["time"]["seconds"]
            return (sec is None, sec if sec is not None else 10**9)
        ev["athletes"].sort(key=sort_key)

    tree = [{
        "season_id": season_id,
        "season_label": season_label,
        "competitions": [{
            "competition_id": competition_id,
            "season_id": season_id,
            "date": date_iso,
            "name": competition_name,
            "name_clean": competition_name_clean,
            "location": location,
            "region": region,
            "pool_type": pool_type,
            "events": sorted(
                events_map.values(),
                key=lambda e: (
                    dims["events"][e["event_id"]].get("distance_m") or 9999,
                    e["base"],
                    0 if not e["category"].lower().startswith("máster") else 1,
                    master_band_key(e["category"]),
                    e["category"],
                    e["sex"]
                )
            )
        }]
    }]

    out = {
        "meta": {
            "version": "1.1.0",
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "timezone": "Europe/Madrid",
            "source": {"file": os.path.basename(pdf_path), "generator": "parse_pdf2tree_pdfplumber.py"}
        },
        "dimensions": {
            "seasons": list(dims["seasons"].values()),
            "clubs": list(dims["clubs"].values()),
            "athletes": list(dims["athletes"].values()),
            "competitions": list(dims["competitions"].values()),
            "events": list(dims["events"].values())
        },
        "tree": tree,
        "results": results_flat
    }
    return out

def merge_season_bundles(bundles: List[Dict], debug: bool = False) -> Dict:
    """
    Fusiona varios outputs de build_tree_json() (cada uno con 1 season y 1 competition)
    en un único output con 1 season y N competitions.
    """
    if not bundles:
        raise ValueError("No hay bundles que fusionar")

    # Tomamos el primero como base
    base = bundles[0]

    # Validación de estructura mínima esperada [1](https://myoffice.accenture.com/personal/mariano_carpintero_accenture_com/Documents/Microsoft%20Copilot%20Chat%20Files/parse_pdf2tree_pdfplumber.py)
    if not base.get("tree") or not base["tree"][0].get("competitions"):
        raise ValueError("Bundle base no tiene tree/competitions")

    base_season_id = base["tree"][0]["season_id"]
    base_season_label = base["tree"][0].get("season_label")

    # Índices por id para evitar duplicados en dimensions
    def index_by_id(lst: List[Dict]) -> Dict[str, Dict]:
        out = {}
        for item in lst:
            _id = item.get("id")
            if _id:
                out[_id] = item
        return out

    dim = base.get("dimensions", {})
    seasons_idx = index_by_id(dim.get("seasons", []))
    clubs_idx = index_by_id(dim.get("clubs", []))
    athletes_idx = index_by_id(dim.get("athletes", []))
    competitions_idx = index_by_id(dim.get("competitions", []))
    events_idx = index_by_id(dim.get("events", []))

    # Para results: evitamos duplicados por id
    results_idx = {r["id"]: r for r in base.get("results", []) if "id" in r}

    # Concat de competiciones en el tree (base ya tiene 1)
    merged_competitions = list(base["tree"][0]["competitions"])

    # Recorremos el resto de bundles
    for b in bundles[1:]:
        if not b.get("tree") or not b["tree"][0].get("competitions"):
            if debug:
                print("WARN: bundle sin tree/competitions, se omite")
            continue

        season_id = b["tree"][0]["season_id"]
        season_label = b["tree"][0].get("season_label")

        # Debe ser la misma temporada (según tu requisito) [1](https://myoffice.accenture.com/personal/mariano_carpintero_accenture_com/Documents/Microsoft%20Copilot%20Chat%20Files/parse_pdf2tree_pdfplumber.py)
        base_file = (base.get("meta", {}).get("source", {}) or {}).get("file", "¿pdf_base?")
        bad_file = (b.get("meta", {}).get("source", {}) or {}).get("file", "¿pdf_desconocido?")

        if season_id != base_season_id:
            raise ValueError(
                "Temporada distinta detectada.\n"
                f"  - PDF base: {base_file} (season_id={base_season_id})\n"
                f"  - PDF con error: {bad_file} (season_id={season_id})\n"
                "Asegúrate de que todos los PDFs son de la misma temporada."
            )

        # Añadir competiciones del tree
        for comp in b["tree"][0]["competitions"]:
            comp_id = comp.get("competition_id")
            # Evita duplicar por competition_id
            if comp_id and any(c.get("competition_id") == comp_id for c in merged_competitions):
                continue
            merged_competitions.append(comp)

        # Merge dimensions por id
        d = b.get("dimensions", {})
        for item in d.get("seasons", []):
            seasons_idx.setdefault(item.get("id"), item)
        for item in d.get("clubs", []):
            clubs_idx.setdefault(item.get("id"), item)
        for item in d.get("athletes", []):
            athletes_idx.setdefault(item.get("id"), item)
        for item in d.get("competitions", []):
            competitions_idx.setdefault(item.get("id"), item)
        for item in d.get("events", []):
            events_idx.setdefault(item.get("id"), item)

        # Merge results por id
        for r in b.get("results", []):
            rid = r.get("id")
            if rid and rid not in results_idx:
                results_idx[rid] = r

    # Ordena competiciones por fecha (si existe)
    def comp_date(c):
        return c.get("date") or "9999-99-99"
    merged_competitions.sort(key=comp_date)

    # Actualiza base
    base["tree"][0]["season_id"] = base_season_id
    if base_season_label and "season_label" in base["tree"][0]:
        base["tree"][0]["season_label"] = base_season_label
    base["tree"][0]["competitions"] = merged_competitions

    base["dimensions"] = {
        "seasons": list(seasons_idx.values()),
        "clubs": list(clubs_idx.values()),
        "athletes": list(athletes_idx.values()),
        "competitions": list(competitions_idx.values()),
        "events": list(events_idx.values())
    }

    base["results"] = list(results_idx.values())

    # Ordena results por fecha (YYYY-MM-DD). Si falta fecha, al final.
    base["results"].sort(key=lambda r: (r.get("date") is None, r.get("date") or "9999-99-99"))

    # Ajusta meta para reflejar merge
    base_meta = base.get("meta", {})
    base_meta["source"] = base_meta.get("source", {})
    base_meta["source"]["generator"] = "parse_pdf2tree_pdfplumber.py (multi-pdf merge)"
    base["meta"] = base_meta

    return base

# ----------------------------
# Main
# ----------------------------

def main():
    ensure_dirs()
    parser = argparse.ArgumentParser(
        description="Convierte un PDF de resultados a JSON con árbol Temporada→Competición→Evento(prueba+sexo+categoría)→Deportistas."
    )
    parser.add_argument("pdf_names", nargs="*", help="Uno o varios PDFs (opcional si usas --glob)")
    parser.add_argument("--glob", dest="pdf_glob", default=None, help="Patrón de PDFs en ./PDF (ej: \"2024*.pdf\" o \"2026*.pdf\")")
    parser.add_argument("--debug", action="store_true", help="Imprime trazas de cabecera y parsing")
    parser.add_argument("--club-filter", action="append", default=None,
                        help="Filtra por clubes que contengan este texto (puede repetirse). Ej: --club-filter Pacifico")
    parser.add_argument("--output", default=None, help="Ruta de salida JSON (por defecto ./JSON/<pdf>_tree.json)")
    args = parser.parse_args()

    invocation = " ".join(sys.argv)

    # Normaliza lista de PDFs
    
    # 1) Resolver lista de PDFs
    pdf_files = []

    expected_end_year = None

    if args.pdf_glob:
        m = re.match(r"^\s*(\d{4})", args.pdf_glob)
        if m:
            expected_end_year = int(m.group(1))
        pattern = os.path.join(".", "PDF", args.pdf_glob)
        pdf_files = sorted(glob(pattern))
        if not pdf_files:
            raise FileNotFoundError(f"No hay PDFs que cumplan el patrón: {pattern}")
    else:
        # Mantiene compatibilidad: permite pasar ficheros manualmente
        if not args.pdf_names:
            raise SystemExit("Debes indicar PDFs (ej: 202404.pdf 202405.pdf) o usar --glob \"2024*.pdf\"")
        for pdf in args.pdf_names:
            base = os.path.basename(pdf)
            if not base.lower().endswith(".pdf"):
                base += ".pdf"
            pdf_files.append(os.path.join(".", "PDF", base))

    # 2) Validar existencia
    input_paths = []
    for p in pdf_files:
        if not os.path.exists(p):
            raise FileNotFoundError(f"No existe el PDF de entrada: {p}")
        input_paths.append(p)
    
    # Decide output
    out_path = args.output
    if not out_path:
        if args.pdf_glob:
            # Ej: "2024*.pdf" -> "2024_tree.json"
            base_name = args.pdf_glob.lower()
            # normaliza el patrón para nombre de fichero (quita extensión y comodines)
            base_name = base_name.replace(".pdf", "")
            base_name = base_name.replace("*", "").replace("?", "")
            base_name = base_name.strip("_- .") or "temporada"
            out_path = os.path.join(".", "JSON", f"{base_name}_tree.json")
        elif len(pdf_files) == 1:
            out_path = os.path.join(".", "JSON", os.path.splitext(os.path.basename(pdf_files[0]))[0] + "_tree.json")
        else:
            out_path = os.path.join(".", "JSON", "temporada_tree.json")

    # Parse + merge
    bundles = []
    skipped = []
    pdf_files_ok = []

    for p in pdf_files:
        try:
            b = build_tree_json(p, debug=args.debug, club_filters=args.club_filter)

            # 1) Validar que el bundle tiene fecha (si date_iso quedó vacío, competition.date estará vacío)
            comp_dim = b.get("dimensions", {}).get("competitions", [])
            comp_date = comp_dim[0].get("date") if comp_dim else None

            if not comp_date:
                print(f"⚠️  SKIP (sin fecha válida): {os.path.basename(p)}")
                skipped.append((os.path.basename(p), "sin fecha válida"))
                continue

            # 2) Validar temporada por fecha contra la esperada del glob (si aplica)
            if expected_end_year is not None:
                actual_end_year = season_end_year_from_date_iso(comp_date)
                if actual_end_year != expected_end_year:
                    print(
                        f"⚠️  SKIP (temporada por fecha {actual_end_year} != esperada {expected_end_year}): "
                        f"{os.path.basename(p)} (fecha={comp_date})"
                    )
                    skipped.append((os.path.basename(p), f"temporada {actual_end_year} != {expected_end_year}"))
                    continue

            bundles.append(b)
            pdf_files_ok.append(p)

        except Exception as e:
            # Cualquier fallo de parsing: avisar y saltar
            print(f"⚠️  SKIP (error parseando): {os.path.basename(p)} -> {e}")
            skipped.append((os.path.basename(p), f"error: {e}"))
            continue

    if not bundles:
        raise SystemExit("No se ha podido procesar ningún PDF del glob (todos fallaron o fueron descartados).")

    data = bundles[0] if len(bundles) == 1 else merge_season_bundles(bundles, debug=args.debug)

    data["results"].sort(key=lambda r: (r.get("date") is None, r.get("date") or "9999-99-99"))

    # (opcional, pero útil) resumen de skips al final
    if skipped:
        print("---- PDFs omitidos ----")
        for f, reason in skipped:
            print(f" - {f}: {reason}")

    inputs = [os.path.basename(p) for p in pdf_files_ok]
    fingerprint = hashlib.sha256(("|".join(sorted(inputs))).encode("utf-8")).hexdigest()[:12]

    with open(out_path, "w", encoding="utf-8") as f:
        data.setdefault("meta", {})
        data["meta"].setdefault("source", {})
        data["meta"]["source"]["invocation"] = invocation
        data["meta"]["source"]["glob"] = args.pdf_glob  # None si no aplica
        data["meta"]["source"]["inputs_resolved"] = inputs
        data["meta"]["source"]["skipped"] = [{"file": f, "reason": r} for f, r in skipped]
        data["meta"]["source"]["inputs_fingerprint"] = fingerprint
        data["meta"]["season_rule"] = "Oct-01..Sep-30 => season_end_year"
        data["meta"]["season_end_year"] = expected_end_year
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"OK -> {out_path}")
    print(f"Resultados: {len(data.get('results', []))}")
    n_events = len(data["dimensions"]["events"])
    n_ath = len(data["dimensions"]["athletes"])
    n_clubs = len(data["dimensions"]["clubs"])
    n_comps = len(data['dimensions']['competitions'])
    print(f"Competiciones: {n_comps} | Eventos: {n_events} | Deportistas: {n_ath} | Clubes: {n_clubs}")

if __name__ == "__main__":
    main()