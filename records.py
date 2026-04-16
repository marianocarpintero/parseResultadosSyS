#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
from pathlib import Path


# ----------------------------
# IO helpers
# ----------------------------

def load_json(path: Path) -> dict:
    # Soporta UTF-8 con y sin BOM
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ----------------------------
# Safe getters for variant shapes
# ----------------------------

def get_nested(d: dict, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def pick_first(*vals):
    for v in vals:
        if v is not None and v != "":
            return v
    return None


# ----------------------------
# Core logic
# ----------------------------

def build_record(competition: dict, event: dict, result: dict, athlete_name: str, club_id: str) -> dict:
    """
    Construye el record EXACTAMENTE con la estructura acordada.
    record_id = "cr_" + <competition_id> + "_" + <event_id> + "_" + <athlete_id>
    """
    competition_id = competition["id"]
    event_id = event["id"]
    athlete_id = result["athlete_id"]

    record_id = f"cr_{competition_id}_{event_id}_{athlete_id}"

    time_obj = result["time"]  # ya normalizado antes

    return {
        "record_id": record_id,
        "athlete": {
            "id": athlete_id,
            "name": athlete_name,
            "club_id": club_id
        },
        "competition": {
            "id": competition_id,
            "season_id": competition.get("season_id"),
            "date": competition.get("date"),
            "name": competition.get("name"),
            "location": competition.get("location"),
            "pool_type": competition.get("pool_type")
        },
        "performance": {
            "event_id": event_id,
            "base": event.get("base"),
            "category": event.get("category"),
            "sex": event.get("sex"),
            "time": {
                "raw": time_obj.get("raw"),
                "display": time_obj.get("display"),
                "seconds": time_obj.get("seconds")
            }
        }
    }


def extract_records(source: dict) -> dict:
    """
    Extrae el record del club: mejor marca histórica (menor tiempo)
    por cada combinación prueba/categoría/sexo.

    En tu modelo, eso está representado por event_id (unívoco),
    por lo que agrupamos por event_id.
    """

    dims = source.get("dimensions") or {}
    athletes = dims.get("athletes") or []
    competitions = dims.get("competitions") or []
    events = dims.get("events") or []

    # Índices para resolver nombres/datos completos
    athlete_name_by_id = {a["id"]: a.get("name") for a in athletes if "id" in a}
    competition_by_id = {c["id"]: c for c in competitions if "id" in c}
    event_by_id = {e["id"]: e for e in events if "id" in e}

    results = source.get("results")
    if results is None:
        # Fallback defensivo (por si en algún merge cambia la clave)
        results = get_nested(source, "data", "results", default=[])

    if results is None:
        print("⚠️  No se encontraron resultados en el JSON de origen.", file=sys.stderr)
        results = []

    best_by_event = {}  # event_id -> (best_seconds, best_result)

    for r in results:
        # 1) Filtrar por status OK
        status = pick_first(r.get("status"), get_nested(r, "performance", "status"))
        if status != "OK":
            continue

        # 2) Obtener time (normalizando variantes)
        time_obj = pick_first(r.get("time"), get_nested(r, "performance", "time"))
        if not isinstance(time_obj, dict):
            continue

        seconds = time_obj.get("seconds")
        if seconds is None:
            continue

        # 3) Obtener IDs esenciales (con tolerancia a variantes)
        event_id = pick_first(
            r.get("event_id"),
            get_nested(r, "performance", "event_id"),
            get_nested(r, "event", "id"),
        )
        competition_id = pick_first(
            r.get("competition_id"),
            get_nested(r, "competition", "id"),
        )
        athlete_id = pick_first(
            r.get("athlete_id"),
            get_nested(r, "athlete", "id"),
        )
        club_id = pick_first(
            r.get("club_id"),
            get_nested(r, "athlete", "club_id"),
            get_nested(r, "athlete", "club", "id"),
        )

        if not event_id or not competition_id or not athlete_id:
            continue

        # Si no hay club_id, seguimos (pero el record quedaría incompleto)
        # Puedes cambiar esto a "continue" si prefieres excluirlos:
        if not club_id:
            club_id = "club_c_d_e_pacifico_salvamento"  # fallback conservador

        # 4) Comparar y guardar mejor
        current = best_by_event.get(event_id)
        if current is None or seconds < current["best_seconds"]:
            best_by_event[event_id] = {
                "best_seconds": seconds,
                "result": {
                    **r,
                    "event_id": event_id,
                    "competition_id": competition_id,
                    "athlete_id": athlete_id,
                    "club_id": club_id,
                    "time": time_obj,
                }
            }

    # 5) Construir records finales con estructura acordada
    records = []
    for event_id, payload in best_by_event.items():
        r = payload["result"]

        competition = competition_by_id.get(r["competition_id"], {"id": r["competition_id"]})
        event = event_by_id.get(event_id, {"id": event_id})

        athlete_name = athlete_name_by_id.get(r["athlete_id"])
        if athlete_name is None:
            # Último fallback (si faltara en dimensions.athletes)
            athlete_name = r.get("athlete_name") or r["athlete_id"]

        record = build_record(
            competition=competition,
            event=event,
            result=r,
            athlete_name=athlete_name,
            club_id=r["club_id"],
        )
        records.append(record)

    # Opcional: ordenar para estabilidad (base, category, sex)
    def sort_key(rec):
        perf = rec.get("performance", {})
        return (perf.get("base") or "", perf.get("category") or "", perf.get("sex") or "")

    records.sort(key=sort_key)

    return {
        "schema_version": "1.0",
        "records": records
    }


def main():
    if len(sys.argv) != 3:
        print("Uso: python records.py <origen.json> <salida.json>", file=sys.stderr)
        sys.exit(1)

    source_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    source = load_json(source_path)
    out = extract_records(source)
    save_json(output_path, out)

    print(f"✅ Records generados: {len(out['records'])}")
    print(f"📄 Escrito: {output_path}")


if __name__ == "__main__":
    main()
