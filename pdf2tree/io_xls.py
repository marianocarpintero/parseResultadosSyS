# pdf2tree/io_xls.py
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from .schema import Season, Competition, Club, Athlete, Event, Result, TimeInfo, Labels
from .builders import DimensionsBuilder, ResultsBuilder
from .trace import TraceSink
from .normalize import (
    normalize_key,
    normalize_title,
    normalize_pool,
    slugify,
    time_raw_to_display_seconds,
    title_case_name_es,
)
from .headers import (
    season_end_year_from_date_iso,
    season_label_from_end_year,
    season_id_from_label,
    clean_name_clean,
)
from .events import build_event_fields


# ----------------------------
# Helpers: columnas Excel
# ----------------------------
def _norm_col(c: str) -> str:
    return " ".join(str(c or "").strip().split()).lower()


def _col(df: pd.DataFrame, *candidates: str) -> Optional[str]:
    """Devuelve el nombre real de columna si existe (tolerante a espacios/case)."""
    wanted = {_norm_col(x) for x in candidates if x}
    for c in df.columns:
        if _norm_col(c) in wanted:
            return c
    return None


def _get(row: pd.Series, col: Optional[str]) -> Any:
    if not col:
        return None
    return row.get(col)


def _to_int(v: Any) -> Optional[int]:
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        s = str(v).strip()
        if s == "":
            return None
        return int(float(s))
    except Exception:
        return None


def _to_str(v: Any) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()


def _to_date_iso(v: Any) -> Optional[str]:
    """Excel -> YYYY-MM-DD (dayfirst)."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        dt = pd.to_datetime(v, dayfirst=True, errors="coerce")
        if pd.isna(dt):
            return None
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def _sex_to_words(sex_value: Any) -> str:
    """Para alimentar build_event_fields (que detecta palabras femen/masc/mixt)."""
    s = _to_str(sex_value).upper()
    if s == "F":
        return "Femenino"
    if s == "M":
        return "Masculino"
    if s == "X":
        return "Mixto"
    # si venía ya como palabra
    return _to_str(sex_value)


def _status_from_exclusion(excl: Any) -> str:
    """Replica la lógica de ex2js: status sale SOLO de 'Exclusión'. [10](https://myoffice.accenture.com/personal/mariano_carpintero_accenture_com/Documents/Microsoft%20Copilot%20Chat%20Files/ex2js.py)"""
    v = _to_str(excl)
    if not v:
        return "OK"
    u = v.upper()
    if "NO FINALIZA" in u:
        return "DNF"
    if "DESCALIFIC" in u:
        return "DSQ"
    if "BAJA" in u:
        return "BAJA"
    return "OK"


def _club_passes(club_name: str, club_filters_norm: List[str]) -> bool:
    if not club_filters_norm:
        return True
    ck = normalize_key(club_name)
    return any(f in ck for f in club_filters_norm)


def _normalize_club_display(club_name: str) -> str:
    """Mismo “arreglo” que hace el parser para C.D.E. [8](https://myoffice.accenture.com/personal/mariano_carpintero_accenture_com/Documents/Microsoft%20Copilot%20Chat%20Files/parser.py)"""
    s = (club_name or "").strip()
    # C.D.E  -> C.D.E.
    import re
    s = re.sub(r"^C\.D\.E\s+", "C.D.E. ", s, flags=re.IGNORECASE)
    s = re.sub(r"^C\.D\.E\.(?=\S)", "C.D.E. ", s, flags=re.IGNORECASE)
    return s


# ----------------------------
# Main XLS processor
# ----------------------------
def process_xls(
    xls_path: str,
    *,
    dims: DimensionsBuilder,
    resb: ResultsBuilder,
    trace: TraceSink,
    club_filters: List[str],
    debug: bool = False,
) -> List[str]:
    """
    Lee XLS y emite Season/Competition/Club/Athlete/Event/Result con el schema de pdf2tree.
    """
    path = Path(xls_path)
    df = pd.read_excel(path, engine="openpyxl")

    # Detectar columnas (tolerante a espacios iniciales)
    c_nombre = _col(df, "Nombre", " Nombre")
    c_apellidos = _col(df, "Apellidos", " Apellidos")
    c_anyo = _col(df, "Año", " Año")
    c_club = _col(df, "Club", " Club")
    c_fecha = _col(df, "Fecha Competición", " Fecha Competición")
    c_lugar = _col(df, "Lugar Competición", " Lugar Competición")
    c_comunidad = _col(df, "Comunidad Competición", " Comunidad Competición")
    c_comp = _col(df, "Competición", " Competición")
    c_tipo_piscina = _col(df, "Tipo Piscina", " Tipo Piscina")
    c_prueba = _col(df, "Prueba", " Prueba")
    c_categoria = _col(df, "Categoría", " Categoría")
    c_sexo = _col(df, "Sexo", " Sexo")
    c_tiempo = _col(df, "Tiempo", " Tiempo")
    c_excl = _col(df, "Exclusión", " Exclusión")
    c_pos = _col(df, "Posición", " Posición")
    c_series = _col(df, "Tipo Serie", " Tipo Serie")

    # cache: competitions por signature para no duplicar
    comp_by_key: Dict[Tuple[str, str, str], str] = {}
    processed_markers: List[str] = []

    club_filters_norm = [normalize_key(x) for x in (club_filters or []) if x]

    for _, row in df.iterrows():
        # --- competition ---
        comp_date = _to_date_iso(_get(row, c_fecha)) or "1970-01-01"
        location_raw = _to_str(_get(row, c_lugar))
        location = normalize_title(location_raw) if location_raw else ""
        comp_name_raw = _to_str(_get(row, c_comp))
        name_clean = clean_name_clean(comp_name_raw)

        # Season según regla Oct–Sep (igual que headers.py) [7](https://myoffice.accenture.com/personal/mariano_carpintero_accenture_com/Documents/Microsoft%20Copilot%20Chat%20Files/headers.py)
        end_year = season_end_year_from_date_iso(comp_date) or 0
        season_label = season_label_from_end_year(end_year) if end_year else "Temporada (desconocida)"
        season_id = season_id_from_label(season_label) if end_year else "s_unknown"
        dims.add_season(Season(id=season_id, label=season_label))

        # comp_id: MISMA fórmula que cli.py (c_ + slugify(date_loc_nameclean)) [1](https://myoffice.accenture.com/personal/mariano_carpintero_accenture_com/Documents/Microsoft%20Copilot%20Chat%20Files/cli.py)
        comp_key = (comp_date, location, name_clean)
        comp_id = comp_by_key.get(comp_key)
        if not comp_id:
            comp_id = "c_" + slugify(f"{comp_date}_{location}_{name_clean}")
            comp_by_key[comp_key] = comp_id

            pool_raw = _to_str(_get(row, c_tipo_piscina))
            pool_type = normalize_pool(pool_raw) if pool_raw else ""

            region_raw = _to_str(_get(row, c_comunidad))
            region = normalize_title(region_raw) if region_raw else ""

            dims.add_competition(
                Competition(
                    id=comp_id,
                    season_id=season_id,
                    name=comp_name_raw,
                    name_clean=name_clean,
                    date=comp_date,
                    date_start=comp_date,
                    date_end=None,
                    location=location,
                    region=region,
                    pool_type=pool_type,
                    source_file=path.name,
                )
            )

        # --- club filter ---
        club_name = _normalize_club_display(_to_str(_get(row, c_club)) or "club_unknown")
        if not _club_passes(club_name, club_filters_norm):
            trace.emit({"action": "SKIP_XLS_ROW_BY_CLUB", "club": club_name, "file": path.name})
            continue

        club_id = "club_" + slugify(club_name)
        dims.add_club(Club(id=club_id, name=club_name, slug=slugify(club_name)))

        # --- athlete ---
        nombre = _to_str(_get(row, c_nombre))
        apellidos = _to_str(_get(row, c_apellidos))
        full_name = title_case_name_es(f"{nombre} {apellidos}".strip())
        birth_year = _to_int(_get(row, c_anyo))
        athlete_id = "a_" + slugify(full_name) + f"_{birth_year if birth_year else 'na'}"
        dims.add_athlete(Athlete(id=athlete_id, name=full_name, birth_year=birth_year))

        # --- event (reutilizando build_event_fields de PDFs para consistencia) [9](https://myoffice.accenture.com/personal/mariano_carpintero_accenture_com/Documents/Microsoft%20Copilot%20Chat%20Files/events.py)[8](https://myoffice.accenture.com/personal/mariano_carpintero_accenture_com/Documents/Microsoft%20Copilot%20Chat%20Files/parser.py)
        prueba = _to_str(_get(row, c_prueba)) or "unknown"
        categoria = _to_str(_get(row, c_categoria))
        sexo_words = _sex_to_words(_get(row, c_sexo))
        category_line = f"{categoria} ({sexo_words})" if categoria else None

        fields = build_event_fields(prueba, category_line)

        # discipline = base sin prefijo "50 m " (misma idea que parser.strip_distance_prefix) [8](https://myoffice.accenture.com/personal/mariano_carpintero_accenture_com/Documents/Microsoft%20Copilot%20Chat%20Files/parser.py)
        import re
        from .parser import DISTANCE_PREFIX_RE
        base = fields["base"]
        discipline = DISTANCE_PREFIX_RE.sub("", base).strip()

        event_obj = Event(
            id=fields["id"],
            base=base,
            discipline=discipline,
            category=fields["category_display"],   # ya en femenino (Absoluta, Máster..., etc.) [9](https://myoffice.accenture.com/personal/mariano_carpintero_accenture_com/Documents/Microsoft%20Copilot%20Chat%20Files/events.py)
            sex=fields["sex"],                     # F/M/X
            relay=fields["relay"],
            distance_m=fields.get("distance_m"),
        )
        dims.add_event(event_obj)

        # --- result ---
        status = _status_from_exclusion(_get(row, c_excl))
        position = _to_int(_get(row, c_pos))
        series_type = _to_str(_get(row, c_series)) or "Final"

        raw_time = _to_str(_get(row, c_tiempo))
        display, seconds = time_raw_to_display_seconds(raw_time) if raw_time else (None, None)
        time_info = TimeInfo(display=display, seconds=seconds, raw=(raw_time if display else None))

        # labels.x igual que parser: "date\ncompetition_name_clean" [8](https://myoffice.accenture.com/personal/mariano_carpintero_accenture_com/Documents/Microsoft%20Copilot%20Chat%20Files/parser.py)
        label_x = f"{comp_date}\n{name_clean}".strip()

        # ID de result: estilo parser individual => incluye series_type [8](https://myoffice.accenture.com/personal/mariano_carpintero_accenture_com/Documents/Microsoft%20Copilot%20Chat%20Files/parser.py)
        rid = "r_" + slugify(f"{comp_id}_{fields['id']}_{athlete_id}_{series_type}")

        resb.add(
            Result(
                id=rid,
                date=comp_date,
                season_id=season_id,
                competition_id=comp_id,
                event_id=fields["id"],
                athlete_id=athlete_id,
                club_id=club_id,
                time=time_info,
                status=status,
                position=position,
                points=None,
                series_type=series_type,
                labels=Labels(x=label_x),
                heat=None,
            )
        )

        trace.emit(
            {
                "action": "XLS_EMIT_RESULT",
                "file": path.name,
                "competition_id": comp_id,
                "event_id": fields["id"],
                "athlete_id": athlete_id,
                "series_type": series_type,
            }
        )

    processed_markers.append(path.name)
    return processed_markers