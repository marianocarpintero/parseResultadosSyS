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
def resolve_pdf_inputs(inputs: List[str], base_dir: str = "./PDF", debug: bool = False) -> List[str]:
    """
    inputs: lista de strings que pueden ser:
      - nombre directo: "2026ddcc.pdf" o "2026ddcc"
      - patrón: "2025*" o "*.pdf" o "2025*.pdf"
    Devuelve lista de rutas completas dentro de base_dir.
    """
    resolved: List[str] = []
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


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------
def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="pdf2tree")
    parser.add_argument(
        "pdf_inputs",
        nargs="*",
        help="PDF(s) o patrones. Ej: 2026ddcc.pdf 2025* *.pdf"
    )
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Si un PDF falla, detiene el proceso.")
    parser.add_argument(
        "--output",
        default="pdf2jsontree.json",
        help="Ruta de salida JSON (por defecto ./JSON/pdf2jsontree.json)"
    )

    # Trazabilidad
    parser.add_argument(
        "--trace",
        default="./JSON/trace/trace.jsonl",
        help="Ruta de salida para trace en JSONL (opcional)."
    )

    # Dump de extract_text (golden dump)
    parser.add_argument("--dump-text", action="store_true", help="Vuelca extract_text() por página.")
    parser.add_argument(
        "--dump-text-dir",
        default="./JSON/dumps",
        help="Directorio donde guardar dumps (por defecto ./JSON/dumps)"
    )

    # Filtros
    parser.add_argument(
        "--club-filter",
        action="append",
        default=None,
        help="Filtra clubes por subcadena (repetible). Ej: --club-filter Pacifico"
    )

    args = parser.parse_args(argv)
    # --- Forzar salida en ./JSON si --output no trae carpeta ---
    if not os.path.isabs(args.output) and os.path.dirname(args.output) == "":
        args.output = os.path.join("./JSON", args.output)
    if args.trace and (not os.path.isabs(args.trace)) and os.path.dirname(args.trace) == "":
        args.trace = os.path.join("./JSON", args.trace)

    ensure_dirs(args.output)
    os.makedirs("./JSON", exist_ok=True)
    os.makedirs(args.dump_text_dir, exist_ok=True)

    # Resolver inputs
    inputs = args.pdf_inputs if args.pdf_inputs else ["*.pdf"]
    pdf_files = resolve_pdf_inputs(inputs, base_dir="./PDF", debug=args.debug)
    if not pdf_files:
        raise SystemExit("No se encontraron PDFs con los patrones indicados en ./PDF")

    # Trace sink
    trace_sink = JsonlTrace(args.trace) if args.trace else NullTrace()

    # Builders
    dims = DimensionsBuilder()
    resb = ResultsBuilder()

    tokenizer = Tokenizer()

    processed: List[str] = []
    skipped: List[Dict[str, str]] = []

    # Contador de competitions para fallback de ids
    comp_counter = 0

    for pdf_path in pdf_files:
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

            # Dump reproducible de extract_text()
            if args.dump_text:
                dump_name = os.path.splitext(os.path.basename(pdf_path))[0] + "_dump.txt"
                dump_path = os.path.join(args.dump_text_dir, dump_name)
                dump_extract_text(pdf_path, dump_path)
                if args.debug:
                    print("DEBUG dump extract_text ->", dump_path)

            # Parsear cabecera (real si existe headers.py, si no fallback)
            competition, season = try_parse_header(pdf_path, debug=args.debug)

            # Construir ids deterministas (si no hay header real, será suficientemente estable)
            season_id = season.get("id", "s_unknown")
            season_label = season.get("label", "Temporada (desconocida)")
            dims.add_season(Season(id=season_id, label=season_label))

            # competition_id: preferimos una slug semántica si hay datos
            comp_date = competition.get("date") or competition.get("date_start") or datetime.now().date().isoformat()
            comp_loc = competition.get("location", "")
            comp_name_clean = competition.get("name_clean", competition.get("name", f"comp_{comp_counter:03d}"))
            comp_id = "c_" + slugify(f"{comp_date}_{comp_loc}_{comp_name_clean}")

            # Registrar competition en dims
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

            # Ejecutar parser single-pass: páginas -> líneas -> tokens -> consume
            for page in iter_pdf_pages(pdf_path):
                for line_no, line in enumerate(page.lines, start=1):
                    line = unicodedata.normalize("NFC", line)
                    tok = tokenizer.classify(page.page_index, line_no, line)
                    parser_sp.consume(
                        tok,
                        competition_id=comp_id,
                        season_id=season_id,
                        date=comp_date
                    )

            # Finalizar (flush de relay si queda abierto)
            parser_sp.finalize(competition_id=comp_id, season_id=season_id, date=comp_date)

            processed.append(os.path.basename(pdf_path))

        except Exception as e:
            msg = f"{os.path.basename(pdf_path)} -> {e}"
            if args.debug:
                print("DEBUG ERROR:", msg)
            skipped.append({"file": os.path.basename(pdf_path), "reason": str(e)})
            if args.strict:
                # cierre trace si aplica
                if args.trace and hasattr(trace_sink, "close"):
                    trace_sink.close()
                raise
            continue

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
            "version": "1.0.0",
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "timezone": "Europe/Madrid",
            "source": {
                "generator": "pdf2tree",
                "inputs": inputs,
                "inputs_resolved": processed,
                "skipped": skipped,
            },
        },
        "dimensions": dims_dict,
        "results": results_list,
        "tree": tree,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    if args.debug:
        print(f"\nDEBUG JSON generado en {args.output}")
        print("DEBUG procesados:", len(processed), "omitidos:", len(skipped))

    # cerrar trace si aplica
    if args.trace and hasattr(trace_sink, "close"):
        trace_sink.close()

    return 0