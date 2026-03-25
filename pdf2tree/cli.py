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


from __future__ import annotations

import os
import json
import argparse
import unicodedata
from glob import glob
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any

from .io_pdf import iter_pdf_pages, dump_extract_text
from .tokenize import Tokenizer
from .parser import SinglePassParser
from .builders import DimensionsBuilder, ResultsBuilder, build_tree, prune_dimensions_by_results, reconcile_athletes_and_results
from .trace import JsonlTrace, NullTrace
from .normalize import slugify, normalize_spaces
from .schema import Season, Competition


# ------------------------------------------------------------
# Utilidades CLI
# ------------------------------------------------------------
def resolve_pdf_inputs(inputs: List[str], debug: bool = False) -> List[str]:
    """
    inputs: lista de strings que pueden ser:
    - nombre directo: "2026mad.pdf" o "2026mad"
    - ruta relativa dentro de ./PDF: "2025-2026/2026mad.pdf"
    - patrón: "2025*" o "*.pdf" o "2025*.pdf"
    La base SIEMPRE es ./PDF salvo que se pase una ruta absoluta.
    """
    base_dir = os.path.normpath("./PDF")

    resolved: List[str] = []
    for raw in inputs:
        raw = (raw or "").strip()
        if not raw:
            continue

        # Normalizar separadores (soporta Windows/Linux)
        raw_norm = raw.replace("\\", "/")

        # Construir path relativo a ./PDF salvo que sea absoluto o ya apunte a ./PDF
        if os.path.isabs(raw_norm):
            base_pattern = raw_norm
        else:
            # permitir que el usuario escriba explícitamente ./PDF/... y no duplicarlo
            if raw_norm.startswith("./PDF/") or raw_norm.startswith("PDF/"):
                base_pattern = raw_norm
            else:
                base_pattern = os.path.join(base_dir, raw_norm)

        # Reglas existentes: añadir .pdf cuando no viene extensión
        if ("*" in base_pattern or "?" in base_pattern) and not base_pattern.lower().endswith(".pdf"):
            pattern = base_pattern + ".pdf"
        elif ("*" not in base_pattern and "?" not in base_pattern) and not base_pattern.lower().endswith(".pdf"):
            pattern = base_pattern + ".pdf"
        else:
            pattern = base_pattern

        matches = glob(pattern)
        if debug:
            print(f"DEBUG resolve pattern: {raw} -> {pattern} -> {len(matches)} matches")
        resolved.extend(matches)

    return sorted(set(resolved))


def ensure_dirs(output_path: str) -> None:
    out_dir = os.path.dirname(output_path) or "."
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs("./PDF", exist_ok=True)


# ------------------------------------------------------------
# Header parsing hook (para que el CLI funcione ya)
# ------------------------------------------------------------
def try_parse_header(pdf_path: str, debug: bool = False) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Intenta usar un parser de cabecera real si existe (recomendado).
    Si no existe todavía en tu refactor, hace fallback a valores mínimos.

    Devuelve:
      competition: dict con campos básicos
      season: dict con {id,label}
    """
    # Hook opcional:
    # - Si has movido tus funciones de cabecera a pdf2tree.headers, las usamos.
    # - Si no, fallback.
    try:
        # Si creas pdf2tree/headers.py con estas funciones, esto se activará.
        from .headers import extract_header_lines, parse_competition_from_header, parse_season_from_header  # type: ignore
        import pdfplumber  # local import para no obligar a headers.py a importarlo aquí

        with pdfplumber.open(pdf_path) as pdf:
            header_lines = extract_header_lines(pdf, debug=debug)
        competition = parse_competition_from_header(header_lines, debug=debug)
        season = parse_season_from_header(header_lines, competition=competition, debug=debug)
        return competition, season

    except Exception as e:
        if debug:
            print("DEBUG header fallback (no headers module o fallo parseando):", str(e))

        # Fallback mínimo: todo lo demás seguirá funcionando.
        # Date: hoy (mejor que None)
        today = datetime.now().date().isoformat()
        competition = {
            "name": os.path.basename(pdf_path),
            "name_clean": os.path.splitext(os.path.basename(pdf_path))[0],
            "location": "",
            "region": "",
            "pool_type": "",
            "date": today,
            "date_start": today,
            "date_end": None,
        }
        # Season fallback
        season = {
            "id": "s_unknown",
            "label": "Temporada (desconocida)",
        }
        return competition, season
# TODO #28 quitar parse_header de aquí y moverlo a headers.py

# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------
def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="pdf2tree")
    parser.add_argument(
        "pdf_inputs",
        nargs="*",
        help="PDF(s) o patrones de entrada. Ej: ./PDF/2026ddcc.pdf ./PDF/2025* ./PDF/*.pdf"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="(opcional) Muestra logs detallados por consola durante el procesamiento."
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="(opcional) Modo estricto: si un PDF falla, se detiene el proceso con error."
    )

    parser.add_argument(
        "--trace",
        action="store_true",
        help="(opcional) Genera un trace JSONL con la trazabilidad del parsing en ./JSON/trace/<salida>.jsonl."
    )

    parser.add_argument(
        "--dump",
        action="store_true",
        help="(opcional) Genera un dump del texto extraído (extract_text) en ./JSON/dump/<salida>.txt."
    )

    parser.add_argument(
        "--club",
        action="append",
        default=["pacifico"],
        help="(opcional) Filtra resultados por club (repetible). "
            "Si no se especifica, se aplica por defecto: pacifico. "
            "Ej: --club Pacifico  (o varios: --club Pacifico --club Canoe)"
    )

    args = parser.parse_args(argv)
    # ------------------------------------------------------------
    # Salida JSON: SIEMPRE en ./JSON/updatePacifico<fecha_ejecución>.json
    # No se expone como argumento (sin override de carpeta/nombre).
    # ------------------------------------------------------------
    os.makedirs("./JSON", exist_ok=True)

    run_stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join("./JSON", f"updatePacifico{run_stamp}.json")
    # Asegura también carpetas auxiliares usadas por el CLI
    ensure_dirs(output_path)

    # ------------------------------------------------------------
    # Trace opcional (flag):
    # - Si NO se especifica --trace => no se crea trace.
    # - Si se especifica --trace => ./JSON/trace/<salida>.jsonl
    #   donde <salida> es el nombre del JSON de salida sin ".json".
    # ------------------------------------------------------------
    trace_path = None
    if args.trace:
        out_base = os.path.basename(output_path)         # updatePacificoYYYYMMDD_HHMMSS.json
        out_stem = os.path.splitext(out_base)[0]         # updatePacificoYYYYMMDD_HHMMSS
        trace_dir = os.path.join("./JSON", "trace")
        os.makedirs(trace_dir, exist_ok=True)            # crea ./JSON/trace si no existe
        trace_path = os.path.join(trace_dir, f"{out_stem}.jsonl")

    # Dump-text
    dump_dir = os.path.join("./JSON", "dump")
    os.makedirs(dump_dir, exist_ok=True)

    # Resolver inputs
    inputs = args.pdf_inputs if args.pdf_inputs else ["*.pdf"]
    pdf_files = resolve_pdf_inputs(inputs, debug=args.debug)
    if not pdf_files:
        raise SystemExit("No se encontraron PDFs con los patrones indicados en ./PDF")

    # Trace sink
    trace_sink = JsonlTrace(trace_path) if trace_path else NullTrace()

    # Builders
    dims = DimensionsBuilder()
    resb = ResultsBuilder()

    tokenizer = Tokenizer()

    processed: List[str] = []
    skipped: List[Dict[str, str]] = []

    # Contador de competitions para fallback de ids
    comp_counter = 0

    for pdf_path in pdf_files:
        parser_sp = None
        comp_id = None
        season_id = None
        comp_date = None

        try:
            parser_sp = SinglePassParser(
                trace=trace_sink,
                on_event=dims.add_event,
                on_result=resb.add,
                on_club=dims.add_club,
                on_athlete=dims.add_athlete,
                club_filters=args.club_filter
            )

            comp_counter += 1
            if args.debug:
                print("\n========================================")
                print("DEBUG procesando:", os.path.basename(pdf_path))
                print("========================================")

            if args.dump_text:
                dump_name = os.path.splitext(os.path.basename(pdf_path))[0] + "_dump.txt"
                dump_path = os.path.join(args.dump_text_dir, dump_name)
                dump_extract_text(pdf_path, dump_path)
                if args.debug:
                    print("DEBUG dump extract_text ->", dump_path)

            competition, season = try_parse_header(pdf_path, debug=args.debug)

            season_id = season.get("id", "s_unknown")
            season_label = season.get("label", "Temporada (desconocida)")
            dims.add_season(Season(id=season_id, label=season_label))

            comp_date = competition.get("date") or competition.get("date_start") or datetime.now().date().isoformat()
            comp_loc = competition.get("location", "")
            comp_name_clean = competition.get("name_clean", competition.get("name", f"comp_{comp_counter:03d}"))
            comp_id = "c_" + slugify(f"{comp_date}_{comp_loc}_{comp_name_clean}")

            dims.add_competition(Competition(
                id=comp_id,
                season_id=season_id,
                name=competition.get("name", ""),
                name_clean=competition.get("name_clean"),
                date=competition.get("date"),
                date_start=competition.get("date_start"),
                date_end=competition.get("date_end"),
                location=competition.get("location", ""),
                region=competition.get("region", ""),
                pool_type=competition.get("pool_type", ""),
                source_file=os.path.basename(pdf_path),
            ))

            for page in iter_pdf_pages(pdf_path):
                # --- IGNORAR PÁGINAS DE CLASIFICACIÓN GENERAL (no son resultados) ---
                page_text_low = (page.text or "").lower()
                if "clasificación general" in page_text_low or "clasificacion general" in page_text_low:
                    if args.debug:
                        print(f"DEBUG skip page {page.page_index} (clasificación general) en {os.path.basename(pdf_path)}")
                    continue

                for line_no, line in enumerate(page.lines, start=1):
                    line = unicodedata.normalize("NFC", line)
                    tok = tokenizer.classify(page.page_index, line_no, line)
                    parser_sp.consume(
                        tok,
                        competition_id=comp_id,
                        season_id=season_id,
                        date=comp_date,
                        competition_name_clean=comp_name_clean
                    )

            processed.append(os.path.basename(pdf_path))

        except Exception as e:
            msg = f"{os.path.basename(pdf_path)} -> {e}"
            if args.debug:
                print("DEBUG ERROR:", msg)
            skipped.append({"file": os.path.basename(pdf_path), "reason": str(e)})

            if args.strict:
                if trace_path and hasattr(trace_sink, "close"):
                    trace_sink.close()
                raise
            continue

        finally:
            # Cerrar/flush SIEMPRE el parser de este PDF
            if parser_sp is not None and comp_id and season_id and comp_date:
                try:
                    parser_sp.finalize(competition_id=comp_id, season_id=season_id, date=comp_date)
                except Exception:
                    pass 

    # Construir salida final
    dims_dict = dims.build()

    if args.debug:
        ev = next((e for e in dims_dict["events"] if e["id"].startswith("e_lanzamiento_de_cuerda_master_30_34")), None)
        print("DEBUG after dims.build:", ev)

    results_list = resb.build()

    # Remapea _na a año si exite, para mejorar conciliación con atletas
    reconcile_athletes_and_results(dims_dict, results_list)

    # filtro de clubes
    dims_dict = prune_dimensions_by_results(dims_dict, results_list)
    if args.debug:
        print("DEBUG resultados:", len(results_list))
        print("DEBUG comps:", len(dims_dict.get("competitions", [])))
        print("DEBUG events:", len(dims_dict.get("events", [])))
        print("DEBUG clubs:", len(dims_dict.get("clubs", [])))
        print("DEBUG athletes:", len(dims_dict.get("athletes", [])))

    tree = build_tree(dims_dict, results_list)

    out = {
        "meta": {
            "version": "1.2.0",
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "timezone": "Europe/Madrid",
            "source": {
                "generator": "pdf2tree",
                "club_filter": args.club_filter,
                "inputs": inputs,
                "inputs_resolved": processed,
                "output": output_path,
                "skipped": skipped,
            },
        },
        "dimensions": dims_dict,
        "results": results_list,
        "tree": tree,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        # Dump opcional: se guarda en ./JSON/dump/<nombre_del_json>.txt
        if args.dump_text:
            dump_name = os.path.basename(output_path) + ".txt"   # p.ej. updatePacifico20260324_153210.json.txt
            dump_path = os.path.join(dump_dir, dump_name)

            out_base = os.path.basename(output_path)
            out_stem = os.path.splitext(out_base)[0]
            dump_path = os.path.join(dump_dir, f"{out_stem}.txt")

            # Sobrescribe una vez y luego concatena
            first = True
            for pdf_path in pdf_files:
                dump_extract_text(pdf_path, dump_path, mode=("w" if first else "a"))
                first = False
            if args.debug:
                print("DEBUG dump extract_text ->", dump_path)

    if args.debug:
        print(f"\nDEBUG JSON generado en {output_path}")
        print("DEBUG procesados:", len(processed), "omitidos:", len(skipped))

    # cerrar trace si aplica
    if args.trace and hasattr(trace_sink, "close"):
        trace_sink.close()

    return 0