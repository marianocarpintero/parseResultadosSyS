#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import json
import argparse
import unicodedata
from datetime import datetime
from typing import List, Dict, Any
from glob import glob

# --- Asegura imports desde la raíz del repo ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from pdf2tree import headers
from pdf2tree.io_text import iter_text_pages  # usa tus fixtures PAGE X/Y
from pdf2tree.tokenize import Tokenizer
from pdf2tree.parser import SinglePassParser
from pdf2tree.builders import (
    DimensionsBuilder,
    ResultsBuilder,
    build_tree,
    prune_dimensions_by_results,
    reconcile_athletes_and_results,
)
from pdf2tree.normalize import slugify
from pdf2tree.schema import Season, Competition


def ensure_dirs() -> None:
    os.makedirs("./JSON", exist_ok=True)
    os.makedirs("./JSON/trace", exist_ok=True)
    os.makedirs("./JSON/dump", exist_ok=True)


def extract_header_lines_from_text_fixture(txt_path: str, debug: bool = False) -> list[str]:
    """
    Devuelve las líneas de cabecera detectadas en el TXT:
    desde la línea que cumple is_header_start hasta la primera línea que cumple is_date_line.
    Solo examina la PRIMERA página del fixture (lo habitual en PDFs reales). [1](https://myoffice.accenture.com/personal/mariano_carpintero_accenture_com/Documents/Microsoft%20Copilot%20Chat%20Files/normalize.py)[2](https://myoffice.accenture.com/personal/mariano_carpintero_accenture_com/Documents/Microsoft%20Copilot%20Chat%20Files/example_valid_minimal.txt)
    """
    first_page = next(iter_text_pages(txt_path), None)
    if not first_page:
        return []

    lines = first_page.lines
    for i, ln in enumerate(lines):
        if headers.is_header_start(ln):  # inicio: RESULTADOS/RESULTS/... [1](https://myoffice.accenture.com/personal/mariano_carpintero_accenture_com/Documents/Microsoft%20Copilot%20Chat%20Files/normalize.py)
            header: list[str] = []
            for j in range(i, len(lines)):
                header.append(lines[j])
                if headers.is_date_line(lines[j]):  # fecha detectada [1](https://myoffice.accenture.com/personal/mariano_carpintero_accenture_com/Documents/Microsoft%20Copilot%20Chat%20Files/normalize.py)
                    if debug:
                        print("[DEBUG] Header lines detectadas:")
                        for x in header:
                            print("  ", x)
                    return header

            # fallback similar a extract_header_lines: si no hay fecha, devuelve un trozo
            return lines[i:i + 12]

    return []


def build_competition_and_season_from_fixture(txt_path: str, debug: bool = False) -> tuple[dict, dict]:
    """
    Usa la cabecera real del TXT para construir competition y season,
    reutilizando headers.parse_competition_from_header y headers.parse_season_from_header. 
    """
    header_lines = extract_header_lines_from_text_fixture(txt_path, debug=debug)
    if header_lines:
        competition = headers.parse_competition_from_header(header_lines, debug=debug)  
        season = headers.parse_season_from_header(header_lines, competition=competition, debug=debug)  
        return competition, season

    # fallback mínimo si el fixture no trae cabecera completa
    today = datetime.now().date().isoformat()
    competition = {
        "name": os.path.basename(txt_path),
        "name_clean": os.path.splitext(os.path.basename(txt_path))[0],
        "location": "FixtureTXT",
        "region": "",
        "pool_type": "",
        "date": today,
        "date_start": today,
        "date_end": None,
    }
    season = {"id": "s_test", "label": "Temporada test"}
    return competition, season


def run_fixtures(fixtures: List[str], club_filters: List[str], debug: bool = False) -> Dict[str, Any]:
    tokenizer = Tokenizer()
    dims = DimensionsBuilder()
    resb = ResultsBuilder()

    season_id = "s_test"
    dims.add_season(Season(id=season_id, label="Temporada test"))

    processed: List[str] = []
    skipped: List[Dict[str, str]] = []

    comp_counter = 0

    for fx in fixtures:
        comp_counter += 1
        try:
            competition, season = build_competition_and_season_from_fixture(fx, debug=debug)

            season_id = season.get("id", "s_unknown")
            season_label = season.get("label", "Temporada (desconocida)")
            dims.add_season(Season(id=season_id, label=season_label))

            comp_date = competition.get("date_start") or competition.get("date") or datetime.now().date().isoformat()
            comp_loc = competition.get("location", "")
            comp_name_clean = competition.get("name_clean", competition.get("name", os.path.splitext(os.path.basename(fx))[0]))

            comp_id = "c_" + slugify(f"{comp_date}_{comp_loc}_{comp_name_clean}_{comp_counter:03d}")

            dims.add_competition(Competition(
                id=comp_id,
                season_id=season_id,
                name=competition["name"],
                name_clean=competition["name_clean"],
                date=competition["date"],
                date_start=competition["date_start"],
                date_end=competition["date_end"],
                location=competition["location"],
                region=competition["region"],
                pool_type=competition["pool_type"],
                source_file=os.path.basename(fx),
            ))

            parser_sp = SinglePassParser(
                trace=None,
                on_event=dims.add_event,
                on_result=resb.add,
                on_club=dims.add_club,
                on_athlete=dims.add_athlete,
                club_filters=club_filters,
            )

            pages_count = 0
            for page in iter_text_pages(fx):
                pages_count += 1
                for line_no, line in enumerate(page.lines, start=1):
                    line = unicodedata.normalize("NFC", line)
                    tok = tokenizer.classify(page.page_index, line_no, line)
                    parser_sp.consume(
                        tok,
                        competition_id=comp_id,
                        season_id=season_id,
                        date=comp_date,
                        competition_name_clean=comp_name_clean,
                    )

            parser_sp.finalize(competition_id=comp_id, season_id=season_id, date=comp_date)

            processed.append(os.path.basename(fx))
            if debug:
                print(f"[OK] {os.path.basename(fx)} pages={pages_count}")

        except Exception as e:
            skipped.append({"file": os.path.basename(fx), "reason": str(e)})
            if debug:
                print(f"[SKIP] {os.path.basename(fx)} -> {e}")

    dims_dict = dims.build()
    results_list = resb.build()

    # Post-proceso igual que tu pipeline: remapeo na, prune y tree
    reconcile_athletes_and_results(dims_dict, results_list)
    dims_dict = prune_dimensions_by_results(dims_dict, results_list)
    tree = build_tree(dims_dict, results_list)

    return {
        "meta": {
            "version": "selftest-txt",
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "timezone": "Europe/Madrid",
            "source": {
                "generator": "tools/txt2json.py",
                "club": club_filters,
                "inputs": fixtures,
                "inputs_resolved": processed,
                "skipped": skipped,
            },
        },
        "dimensions": dims_dict,
        "results": results_list,
        "tree": tree,
    }


def resolve_txt_inputs(raw_inputs: list[str]) -> list[str]:
    """
    Expande patrones (*.txt) y directorios.
    - Si es directorio => añade *.txt dentro.
    - Si hay wildcard => usa glob().
    - Si es fichero => lo usa tal cual si existe.
    """
    resolved: list[str] = []
    for raw in raw_inputs:
        raw = (raw or "").strip()
        if not raw:
            continue

        # Directorio => *.txt
        if os.path.isdir(raw):
            resolved.extend(glob(os.path.join(raw, "*.txt")))
            continue

        # Patrón (wildcards)
        if "*" in raw or "?" in raw:
            resolved.extend(glob(raw))
            continue

        # Fichero directo
        if os.path.exists(raw):
            resolved.append(raw)

    # solo .txt y sin duplicados
    resolved = [p for p in resolved if p.lower().endswith(".txt")]
    return sorted(set(resolved))


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="txt2json")
    ap.add_argument("fixtures", nargs="+", help="Ruta(s)/patrones a fixtures .txt (ej: tests/fixtures/text/*.txt)")
    ap.add_argument("--debug", action="store_true", help="(opcional) Logs detallados")
    ap.add_argument("--club", action="append", default=["pacifico"],
                    help="(opcional) Filtro de club (repetible). Default: pacifico")
    ap.add_argument("--out", default=None,
                    help="(opcional) Ruta de salida JSON. Si no se especifica: ./JSON/selftest_<timestamp>.json")

    args = ap.parse_args(argv)

    ensure_dirs()

    ts = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    out_path = args.out or os.path.join("./JSON", f"selftest_{ts}.json")

    fixtures = resolve_txt_inputs(args.fixtures)
    if not fixtures:
        raise SystemExit("No se encontraron fixtures .txt con los patrones/rutas indicados.")

    data = run_fixtures(fixtures, club_filters=args.club, debug=args.debug)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"JSON generado: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())