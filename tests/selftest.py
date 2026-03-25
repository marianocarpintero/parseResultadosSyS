#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import Any

from pdf2tree.io_text import iter_text_pages
from pdf2tree.tokenize import Tokenizer
from pdf2tree.parser import SinglePassParser
from pdf2tree.builders import (
    DimensionsBuilder,
    ResultsBuilder,
    prune_dimensions_by_results,
    reconcile_athletes_and_results,
    build_tree,
)
from pdf2tree.schema import Season, Competition
from pdf2tree.normalize import slugify

# Para asserts de cabecera (sin PDF real)
from pdf2tree import headers


FIXTURE_DIR = os.path.join("tests", "fixtures", "text")

# -----------------------------
# Specs por fixture (aserts específicos)
# -----------------------------
FIXTURE_SPECS: dict[str, dict[str, Any]] = {
    # 1) Cabecera con "DEFINITIVOS" y dash final + un evento mínimo
    "header_definitivos_guion.txt": {
        "expect_results": 1,
        "expect_events": 1,
        "header_expect": {
            "name_clean": "VI Abierto De Madrid De Salvamento Y Socorrismo",
            "location": "Centro Deportivo M86",
            "date_start": "2026-03-15",
        },
    },

    # 2) Doble máster por rangos: un título con 60-64 y 70-74
    "master_multiple.txt": {
        "expect_results": 2,
        "expect_events": 2,
        "expect_event_categories": {"Máster 60-64", "Máster 70-74"},
        "forbid_event_id_substrings": ["60_64y70_74", "60_64_y_70_74"],
    },

    # 3) Relevo 4 miembros cruzando página + ruido con coma/dígitos (debe ignorarse)
    "relay_cross_page.txt": {
        "expect_pages": 2,
        "expect_results": 4,  # 1 equipo -> 4 resultados (uno por miembro)
        "expect_events": 1,
        "expect_all_results": {
            "status": "OK",
            "position": 1,
            "time_raw": "02:41:73",
        },
    },

    "individual_statuses_non_ok.txt": {
    "expect_events": 2,  # (hay evento repetido en dos páginas; según tu parser puede ser 1 si lo deduplica)
    "expect_results": 4,
    },

    "line_throw_two_members_cross_page.txt": {
    "expect_events": 1,
    "expect_results": 2,
    },

    "relay_incomplete_then_new_event_flush.txt": {
    "expect_events": 2,
    "expect_results": 4,
    },
}


# -----------------------------
# Helpers de cabecera sobre TXT (sin pdfplumber)
# -----------------------------
def extract_header_lines_from_text(txt_path: str) -> list[str]:
    """
    Replica la lógica de headers.extract_header_lines() pero sobre un fixture TXT.
    Busca desde la primera línea que sea is_header_start hasta la primera línea is_date_line.
    """  # headers.is_header_start/is_date_line existen en headers.py 
    for page in iter_text_pages(txt_path):
        # page.lines ya vienen normalizadas como iter_pdf_pages() 
        lines = page.lines
        for i, ln in enumerate(lines):
            if headers.is_header_start(ln):  
                header: list[str] = []
                for j in range(i, len(lines)):
                    header.append(lines[j])
                    if headers.is_date_line(lines[j]):  
                        return header
                # Si no encuentra fecha, devuelve un trozo (mismo espíritu que el fallback original)
                return lines[i:i + 12]
    return []


# -----------------------------
# Helpers
# -----------------------------
def count_pages(txt_path: str) -> int:
    """Cuenta cuántas páginas hay en el fixture TXT."""
    return sum(1 for _ in iter_text_pages(txt_path))


def athletes_by_id(out: dict) -> dict[str, dict]:
    """Index rápido: athlete_id -> athlete dict (name, birth_year...)."""
    return {a["id"]: a for a in out["dimensions"].get("athletes", []) if a.get("id")}


def events_by_id(out: dict) -> dict[str, dict]:
    """Index rápido: event_id -> event dict."""
    return {e["id"]: e for e in out["dimensions"].get("events", []) if e.get("id")}


def clubs_by_id(out: dict) -> dict[str, dict]:
    """Index rápido: club_id -> club dict."""
    return {c["id"]: c for c in out["dimensions"].get("clubs", []) if c.get("id")}


def result_time_raw(r: dict) -> str | None:
    t = r.get("time") or {}
    return t.get("raw")


def build_fixture_summary(txt_path: str, out: dict) -> dict:
    dims = out["dimensions"]
    return {
        "fixture": os.path.basename(txt_path),
        "pages": (out.get("_selftest", {}) or {}).get("pages", -1),
        "events": len(dims.get("events", [])),
        "results": len(out.get("results", [])),
        "athletes": len(dims.get("athletes", [])),
        "clubs": len(dims.get("clubs", [])),
    }

# -----------------------------
# Pipeline E2E sobre TXT
# -----------------------------
def run_case(txt_path: str, *, club_filters: list[str] | None = None, debug: bool = False) -> dict:
    if club_filters is None:
        club_filters = ["pacifico"]

    dims = DimensionsBuilder()
    resb = ResultsBuilder()
    tokenizer = Tokenizer()

    # Competition/season deterministas para test
    today = "2026-03-15"
    season_id = "s_test_2025_2026"
    comp_name_clean = f"Selftest {os.path.splitext(os.path.basename(txt_path))[0]}"
    comp_loc = "TestLab"
    comp_id = "c_" + slugify(f"{today}_{comp_loc}_{comp_name_clean}")

    dims.add_season(Season(id=season_id, label="Temporada test 2025-2026"))
    dims.add_competition(
        Competition(
            id=comp_id,
            season_id=season_id,
            name=comp_name_clean,
            name_clean=comp_name_clean,
            date=today,
            date_start=today,
            date_end=None,
            location=comp_loc,
            region="",
            pool_type="",
            source_file=os.path.basename(txt_path),
        )
    )

    parser_sp = SinglePassParser(
        trace=None,
        on_event=dims.add_event,
        on_result=resb.add,
        on_club=dims.add_club,
        on_athlete=dims.add_athlete,
        club_filters=club_filters,
    )

    pages_count = 0
    for page in iter_text_pages(txt_path):
        pages_count += 1
        for line_no, line in enumerate(page.lines, start=1):
            tok = tokenizer.classify(page.page_index, line_no, line)
            parser_sp.consume(
                tok,
                competition_id=comp_id,
                season_id=season_id,
                date=today,
                competition_name_clean=comp_name_clean,
            )

    parser_sp.finalize(competition_id=comp_id, season_id=season_id, date=today)

    dims_dict = dims.build()
    results_list = resb.build()

    reconcile_athletes_and_results(dims_dict, results_list)
    dims_dict = prune_dimensions_by_results(dims_dict, results_list)
    tree = build_tree(dims_dict, results_list)

    out = {
        "meta": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source_fixture": txt_path,
        },
        "dimensions": dims_dict,
        "results": results_list,
        "tree": tree,
        "_selftest": {"pages": pages_count},
    }

    if debug:
        print(f"[DEBUG] {os.path.basename(txt_path)} -> results={len(results_list)} "
              f"events={len(dims_dict.get('events', []))} "
              f"clubs={len(dims_dict.get('clubs', []))} "
              f"athletes={len(dims_dict.get('athletes', []))}")

    return out


# -----------------------------
# Asserts generales
# -----------------------------
def assert_basic_invariants(out: dict) -> None:
    dims = out["dimensions"]
    results = out["results"]

    assert isinstance(results, list), "results debe ser una lista"

    event_ids = {e["id"] for e in dims.get("events", []) if e.get("id")}
    club_ids = {c["id"] for c in dims.get("clubs", []) if c.get("id")}
    athlete_ids = {a["id"] for a in dims.get("athletes", []) if a.get("id")}
    comp_ids = {c["id"] for c in dims.get("competitions", []) if c.get("id")}

    assert len(comp_ids) == 1, "en selftest esperamos 1 competition"
    assert len(event_ids) >= 1, "no hay events en dimensions (fixture quizá sin tabla)"
    assert len(club_ids) >= 1, "no hay clubs en dimensions"
    assert len(athlete_ids) >= 1, "no hay athletes en dimensions"

    # Referencias básicas
    for r in results:
        assert r.get("competition_id") in comp_ids, f"result sin competition válida: {r.get('id')}"
        assert r.get("event_id") in event_ids, f"result sin event válido: {r.get('id')}"
        assert r.get("club_id") in club_ids, f"result sin club válido: {r.get('id')}"
        assert r.get("athlete_id") in athlete_ids, f"result sin athlete válido: {r.get('id')}"
        assert r.get("id"), "result sin id"

    # Unicidad de result.id
    rids = [r.get("id") for r in results]
    assert len(rids) == len(set(rids)), "hay result.id duplicados (posible bug en generación)"


# -----------------------------
# Asserts por fixture
# -----------------------------
def assert_per_fixture(txt_path: str, out: dict) -> None:
    fname = os.path.basename(txt_path)
    spec = FIXTURE_SPECS.get(fname, {})

    # counts
    if "expect_results" in spec:
        assert len(out["results"]) == spec["expect_results"], (
            f"{fname}: results esperados={spec['expect_results']} obtenidos={len(out['results'])}"
        )

    if "expect_events" in spec:
        ev_count = len(out["dimensions"].get("events", []))
        assert ev_count == spec["expect_events"], (
            f"{fname}: events esperados={spec['expect_events']} obtenidos={ev_count}"
        )

    # header expectations (testea parse_competition_from_header sobre TXT)
    if "header_expect" in spec:
        header_lines = extract_header_lines_from_text(txt_path)
        assert header_lines, f"{fname}: no se detectó cabecera (RESULTADOS...fecha) en el fixture"
        comp = headers.parse_competition_from_header(header_lines, debug=False)
        exp = spec["header_expect"]
        if "name_clean" in exp:
            assert comp.get("name_clean") == exp["name_clean"], (
                f"{fname}: name_clean='{comp.get('name_clean')}' esperado='{exp['name_clean']}'"
            )
        if "location" in exp:
            assert comp.get("location") == exp["location"], (
                f"{fname}: location='{comp.get('location')}' esperado='{exp['location']}'"
            )
        if "date_start" in exp:
            assert comp.get("date_start") == exp["date_start"], (
                f"{fname}: date_start='{comp.get('date_start')}' esperado='{exp['date_start']}'"
            )

    # expected event categories display
    if "expect_event_categories" in spec:
        cats = {e.get("category") for e in out["dimensions"].get("events", []) if e.get("category")}
        missing = set(spec["expect_event_categories"]) - cats
        assert not missing, f"{fname}: faltan categorías esperadas: {sorted(missing)}; vistas={sorted(cats)}"

    # forbid event_id substrings (asegura que no se coló la categoría múltiple en el id)
    if "forbid_event_id_substrings" in spec:
        for e in out["dimensions"].get("events", []):
            eid = e.get("id", "")
            for bad in spec["forbid_event_id_substrings"]:
                assert bad not in eid, f"{fname}: event_id contiene substring prohibida '{bad}': {eid}"

    # all results must share expected fields
    if "expect_all_results" in spec:
        exp = spec["expect_all_results"]
        for r in out["results"]:
            if "status" in exp:
                assert r.get("status") == exp["status"], f"{fname}: status inesperado en {r.get('id')}"
            if "position" in exp:
                assert r.get("position") == exp["position"], f"{fname}: position inesperada en {r.get('id')}"
            if "time_raw" in exp:
                raw = (r.get("time") or {}).get("raw")
                assert raw == exp["time_raw"], f"{fname}: time.raw inesperado en {r.get('id')} -> {raw}"

    if "expect_pages" in spec:
        assert count_pages(txt_path) == spec["expect_pages"], f"{fname}: páginas esperadas={spec['expect_pages']}"


def check_header_definitivos_guion(txt_path: str, out: dict) -> None:
    header_lines = extract_header_lines_from_text(txt_path)
    assert header_lines, "No se detectó cabecera en PAGE 1"

    comp = headers.parse_competition_from_header(header_lines, debug=False)  # [2](https://myoffice.accenture.com/personal/mariano_carpintero_accenture_com/Documents/Microsoft%20Copilot%20Chat%20Files/trace.py)

    # No debe contener "Definitivos"
    assert "Definitivos" not in (comp.get("name") or ""), "La cabecera contiene 'Definitivos' en name"
    assert "Definitivos" not in (comp.get("name_clean") or ""), "La cabecera contiene 'Definitivos' en name_clean"

    # No debe acabar en '-' (guion suelto)
    assert not (comp.get("name_clean") or "").strip().endswith("-"), "name_clean termina con '-'"

    # Y valida campos clave si quieres reforzarlo
    assert comp.get("location") == "Centro Deportivo M86", "Location incorrecta en cabecera"
    assert comp.get("date_start") == "2026-03-15", "date_start incorrecta en cabecera"

def check_master_multiple(txt_path: str, out: dict) -> None:
    events = out["dimensions"].get("events", [])
    assert len(events) == 2, "Se esperaban 2 events (60-64 y 70-74)"

    eids = [e["id"] for e in events]
    assert len(set(eids)) == 2, "Los event_id deben ser distintos"

    # No debe haber id combinado tipo 60_64y70_74
    for eid in eids:
        assert "60_64y70_74" not in eid and "60_64_y_70_74" not in eid, f"event_id combinado: {eid}"

    # Categorías esperadas (display)
    cats = {e.get("category") for e in events}
    assert "Máster 60-64" in cats, f"Falta categoría 'Máster 60-64' (cats={cats})"
    assert "Máster 70-74" in cats, f"Falta categoría 'Máster 70-74' (cats={cats})"

def check_relay_cross_page(txt_path: str, out: dict) -> None:
    results = out["results"]
    assert len(results) == 4, f"Relevo 4x50 debe generar 4 results, got={len(results)}"  # [2](https://myoffice.accenture.com/personal/mariano_carpintero_accenture_com/Documents/Microsoft%20Copilot%20Chat%20Files/trace.py)

    for r in results:
        assert r.get("status") == "OK", "En este fixture el status debe ser OK"
        assert r.get("position") == 1, "En este fixture la posición del equipo debe ser 1"
        assert result_time_raw(r) == "02:41:73", f"time.raw inesperado: {result_time_raw(r)}"

    # Ningún atleta debe tener nombre de dirección/ruido
    a_by_id = athletes_by_id(out)
    names = {a_by_id[r["athlete_id"]]["name"] for r in results if r.get("athlete_id") in a_by_id}
    for n in names:
        assert "Av." not in n and "28703" not in n, f"Se coló ruido como atleta: {n}"
    
def check_individual_statuses_non_ok(txt_path: str, out: dict) -> None:
    results = out["results"]
    assert len(results) == 4, "Se esperaban 4 resultados (OK + DSQ + DNS + BAJA)"

    statuses = [r.get("status") for r in results]
    # Ajusta estos valores a tu mapping real de parse_status()
    assert "OK" in statuses, "Falta status OK"
    assert "DSQ" in statuses, "Falta status DSQ"
    assert "DNS" in statuses or "DNS" in statuses, "Falta status DNS (No Presentado)"
    assert "BAJA" in statuses, "Falta status BAJA"

    # En no OK, el tiempo suele ser None (según tu política)
    for r in results:
        if r.get("status") != "OK":
            assert (r.get("time") or {}).get("raw") in (None, ""), f"Tiempo debería ser None en {r.get('status')}"

def check_line_throw_two_members(txt_path: str, out: dict) -> None:
    events = out["dimensions"].get("events", [])
    assert len(events) == 1, "Debe haber 1 evento"

    ev = events[0]
    assert ev.get("base") == "Lanzamiento de Cuerda", f"Base inesperada: {ev.get('base')}"
    assert ev.get("relay") is True, "Lanzamiento de cuerda debe ser relay"
    assert ev.get("distance_m") in (None, ""), "Lanzamiento de cuerda no tiene distancia"

    results = out["results"]
    assert len(results) == 2, "Lanzamiento de cuerda debe generar 2 results (2 miembros)"  

def check_relay_incomplete_then_new_event_flush(txt_path: str, out: dict) -> None:
    events = out["dimensions"].get("events", [])
    assert len(events) == 2, f"Se esperaban 2 eventos, got={len(events)}"

    results = out["results"]
    # En el fixture había 3 miembros de relevo + 1 individual = 4 (si tu parser emite parciales)
    assert len(results) == 4, f"Se esperaban 4 results (3 relay parciales + 1 individual), got={len(results)}"


FIXTURE_CHECKS = {
    "header_definitivos_guion.txt": check_header_definitivos_guion,
    "master_multiple.txt": check_master_multiple,
    "relay_cross_page.txt": check_relay_cross_page,

    # Si añades los otros fixtures:
    "individual_statuses_non_ok.txt": check_individual_statuses_non_ok,
    "line_throw_two_members_cross_page.txt": check_line_throw_two_members,
    "relay_incomplete_then_new_event_flush.txt": check_relay_incomplete_then_new_event_flush,
}


###########################################################################################################
#
# - - -   MAIN   - - -
#
###########################################################################################################
def main() -> int:
    # Por defecto, ejecuta todos los fixtures declarados en FIXTURE_SPECS
    fixtures = list(FIXTURE_SPECS.keys())

    # Permitir ejecutar solo uno: python tests/selftest.py relay_cross_page.txt
    if len(sys.argv) > 1:
        fixtures = [sys.argv[1]]

    ok = 0
    fail = 0
    summaries = []

    for fx in fixtures:
        path = fx if os.path.isabs(fx) else os.path.join(FIXTURE_DIR, fx)
        if not os.path.exists(path):
            print(f"[SKIP] No existe fixture: {path}")
            continue

        try:
            out = run_case(path, club_filters=["pacifico"], debug=False)
            assert_basic_invariants(out)
            assert_per_fixture(path, out)
            # Asserts específicos del fixture (si existen)
            fname = os.path.basename(path)
            chk = FIXTURE_CHECKS.get(fname)
            if chk:
                chk(path, out)

            summary = build_fixture_summary(path, out)
            summaries.append(("OK", summary))

            print(f"[OK ] {summary['fixture']}")
            print(
                f"      pages={summary['pages']}  "
                f"events={summary['events']}  "
                f"results={summary['results']}  "
                f"athletes={summary['athletes']}  "
                f"clubs={summary['clubs']}"
            )
            ok += 1

        except AssertionError as ae:
            summaries.append(("FAIL", {"fixture": os.path.basename(path), "reason": str(ae)}))
            print(f"[FAIL] {os.path.basename(path)}")
            print(f"      reason: {ae}")
            fail += 1

        except Exception as e:
            summaries.append(("ERROR", {"fixture": os.path.basename(path), "reason": str(e)}))
            print(f"[ERROR] {os.path.basename(path)}")
            print(f"      reason: {type(e).__name__}: {e}")
            fail += 1

    print(f"\nResumen: OK={ok} FAIL={fail}")
    print("=" * 50)
    print("SELFTEST SUMMARY")
    print(f"fixtures: {len(summaries)}   OK: {ok}   FAIL: {fail}")
    print("=" * 50)

    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())