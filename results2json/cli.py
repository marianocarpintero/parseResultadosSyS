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

############################################################
# cli.py se encargar de:
# 
# - parsear argumentos
# - resolver rutas de entrada/salida
# - orquestar el pipeline (crear tokenizer/parser/builders, iterar PDFs/páginas)
############################################################


from __future__ import annotations

import os
import json
import argparse
import unicodedata
from glob import glob
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any

from .io_pdf import iter_pdf_pages, dump_extract_text
from .io_text import iter_text_pages
from .io_xls import process_xls
from .tokenize import Tokenizer
from .parser import SinglePassParser
from .builders import DimensionsBuilder, ResultsBuilder, build_tree, prune_dimensions_by_results, reconcile_athletes_and_results
from .trace import JsonlTrace, NullTrace
from .normalize import slugify, normalize_spaces
from .schema import Season, Competition
from .headers import try_parse_header


# ------------------------------------------------------------
# Utilidades CLI
# ------------------------------------------------------------
def resolve_inputs(inputs: List[str], debug: bool = False, allow_txt: bool = False) -> List[str]:
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
        raw_low = raw_norm.lower()

        # ################################################
        #  
        # --- NUEVO: TXT fixture ---
        # --- Se usa para probar nuevos formatos de PDF simulándolos con TXT ---
        #
        # #################################################
        if allow_txt and (raw_low.endswith(".txt") or raw_low.endswith("*.txt")):
            # patrón con wildcards
            if "*" in raw_norm or "?" in raw_norm:
                matches = glob(raw_norm)
                if debug:
                    print(f"DEBUG resolve TXT pattern: {raw} -> {raw_norm} -> {len(matches)} matches")
                resolved.extend(matches)
            else:
                # fichero directo
                if os.path.exists(raw_norm):
                    resolved.append(raw_norm)
                    if debug:
                        print(f"DEBUG resolve TXT file: {raw} -> OK")
                else:
                    if debug:
                        print(f"DEBUG resolve TXT file: {raw} -> NOT FOUND")
            continue


        # ################################################
        #
        # --- NUEVO: XLS / XLSX / XLSM ---
        #
        # #################################################
        EXCEL_EXTS = (".xlsx", ".xlsm", ".xls")

        is_excel = raw_low.endswith(EXCEL_EXTS) or raw_low.endswith(("*.xlsx", "*.xlsm", "*.xls"))
        if is_excel:
            candidates: List[str] = []

            # Caso 1: ruta absoluta o el usuario ya puso carpeta (./PDF/..., PDF/..., ./XLS/..., etc.)
            # En ese caso, respeta tal cual.
            if os.path.isabs(raw_norm) or ("/" in raw_norm):
                candidates = [raw_norm]
            else:
                # Caso 2: patrón/archivo sin ruta -> buscamos en carpetas "convención" y también cwd
                candidates = [
                    os.path.join("./XLS", raw_norm),
                    os.path.join("./PDF", raw_norm),
                    raw_norm,
                ]

            matches_all: List[str] = []
            for cand in candidates:
                if "*" in cand or "?" in cand:
                    m = glob(cand)
                else:
                    m = [cand] if os.path.exists(cand) else []
                if debug:
                    print(f"DEBUG resolve XLS: {raw} -> {cand} -> {len(m)} matches")
                matches_all.extend(m)

            resolved.extend(matches_all)
            continue

        # ################################################
        #  
        # --- Proceso habitual de PDF ---
        #
        # #################################################
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
    os.makedirs("./XLS", exist_ok=True)


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------
def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="results2json")
    parser.add_argument(
        "inputs",
        nargs="*",
        help="Inputs normales: PDF/XLS/XLSX/XLSM. Patrones dentro de ./PDF o rutas directas. "
            "TXT solo en modo tests con --allow-txt."
    )

    parser.add_argument(
        "--club",
        action="append",
        default=["pacifico"],
        help="(opcional) Filtra resultados por club (repetible). "
            "Si no se especifica, se aplica por defecto: pacifico. "
            "Ej: --club Pacifico  (o varios: --club Pacifico --club Canoe)"
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="(opcional) Modo estricto: si un PDF falla, se detiene el proceso con error."
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="(opcional) Muestra logs detallados por consola durante el procesamiento."
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
        "--allow-txt",
        action="store_true",
        help="(solo tests) Permite procesar fixtures .txt con formato dump. Por defecto NO se aceptan .txt."
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
    inputs = args.inputs if args.inputs else ["*.pdf", "*.xlsx", "*.xls", "*.xlsm"]
    input_files = resolve_inputs(inputs, debug=args.debug, allow_txt=args.allow_txt)

    if not input_files:
        raise SystemExit("No se encontraron archivos de entrada (PDF/XLS/XLSX/XLSM)")

# TODO #39 No se encuentran ficheros cuando sólo hay xlsx.

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

    for input_path in input_files:
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
                club_filters=args.club
            )

            comp_counter += 1
            if args.debug:
                print("\n========================================")
                print("DEBUG procesando:", os.path.basename(input_path))
                print("========================================")

            competition, season = try_parse_header(input_path, debug=args.debug)

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
                source_file=os.path.basename(input_path),
            ))

            # --- NUEVO: XLS ---
            if input_path.lower().endswith((".xlsx", ".xlsm", ".xls")):
                processed_x = process_xls(
                    input_path,
                    dims=dims,
                    resb=resb,
                    trace=trace_sink,
                    club_filters=args.club,
                    debug=args.debug,
                )
                processed.extend(processed_x)
                continue

            if input_path.lower().endswith(".txt"):
                if not args.allow_txt:
                    raise ValueError("Input .txt no permitido en modo normal. Usa tools/txt2json.py o --allow-txt")
                page_iter = iter_text_pages(input_path)

            elif input_path.lower().endswith(".pdf"):
                page_iter = iter_pdf_pages(input_path)
            else:
                raise ValueError("Tipo de fichero no admitido.\nInputs normales: PDF/XLS/XLSX/XLSM. Patrones dentro de ./PDF o rutas directas.\nTXT solo en modo tests con --allow-txt.")

            for page in page_iter:
                # --- IGNORAR PÁGINAS DE CLASIFICACIÓN GENERAL (no son resultados) ---
                page_text_low = (page.text or "").lower()
                if "clasificación general" in page_text_low or "clasificacion general" in page_text_low:
                    if args.debug:
                        print(f"DEBUG skip page {page.page_index} (clasificación general) en {os.path.basename(input_path)}")
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

            processed.append(os.path.basename(input_path))

        except Exception as e:
            msg = f"{os.path.basename(input_path)} -> {e}"
            if args.debug:
                print("DEBUG ERROR:", msg)
            skipped.append({"file": os.path.basename(input_path), "reason": str(e)})

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
                "generator": "results2json",
                "club": args.club,
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

        # Dump opcional: se guarda en ./JSON/dump/<salida>.txt
        # Requisito: si el input es TXT, --dump NO hace nada.
        if args.dump:
            pdf_only = [p for p in input_files if p.lower().endswith(".pdf")]
            if pdf_only:
                out_base = os.path.basename(output_path)
                out_stem = os.path.splitext(out_base)[0]
                dump_path = os.path.join(dump_dir, f"{out_stem}.txt")

                first = True
                for p in pdf_only:
                    dump_extract_text(p, dump_path, mode=("w" if first else "a"))
                    first = False

                if args.debug:
                    print("DEBUG dump extract_text ->", dump_path)
            else:
                if args.debug:
                    print("DEBUG dump omitido: no hay PDFs (solo TXT).")

    if args.debug:
        print(f"\nDEBUG JSON generado en {output_path}")
        print("DEBUG procesados:", len(processed), "omitidos:", len(skipped))

    # cerrar trace si aplica
    if args.trace and hasattr(trace_sink, "close"):
        trace_sink.close()

    return 0