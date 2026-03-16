#!/usr/bin/env python3
"""merge_pacifico.py

CLI para fusionar (merge) dos JSONs del proyecto Pacifico.

Características:
- Merge por ID en dimensions (seasons, clubs, athletes, competitions, events)
- Merge por ID en results
- Merge de tree con indexación (rápido) y deduplicación por atleta + serie + heat
- Validación post-merge (estructura + referencias cruzadas)

Uso típico:
  python merge_pacifico.py --base ./JSON/Pacifico.json --new ./JSON/2025-2026.json --out ./JSON/Pacifico_merged.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pacifico_merge.merger import merge_pacifico
from pacifico_merge.validate import validate_pacifico


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='merge_pacifico.py',
        description='Fusiona (merge) dos datasets JSON de Pacifico, evitando duplicados por id.'
    )

    p.add_argument('--base', type=Path, required=True,
                   help='Ruta al JSON base/histórico (p.ej. ./JSON/Pacifico.json)')
    p.add_argument('--new', dest='new_json', type=Path, required=True,
                   help='Ruta al JSON nuevo a integrar (p.ej. ./JSON/2025-2026.json)')
    p.add_argument('--out', type=Path, required=True,
                   help='Ruta del JSON de salida (p.ej. ./JSON/Pacifico_merged.json)')

    p.add_argument('--no-merge-tree', action='store_true',
                   help='No fusionar el bloque tree (solo dimensions + results).')

    p.add_argument('--validate', action='store_true', default=True,
                   help='Ejecutar validación post-merge (por defecto: activado).')
    p.add_argument('--no-validate', action='store_true',
                   help='Desactivar validación post-merge.')

    p.add_argument('--strict', action='store_true',
                   help='Modo estricto: cualquier error de validación devuelve exit code != 0.')

    p.add_argument('--report', type=Path, default=None,
                   help='Opcional: ruta donde guardar un informe JSON de merge/validación.')

    return p


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    do_merge_tree = not args.no_merge_tree
    do_validate = args.validate and not args.no_validate

    merged, merge_report = merge_pacifico(
        base_path=args.base,
        new_path=args.new_json,
        out_path=args.out,
        merge_tree=do_merge_tree,
    )

    validation_report = None
    if do_validate:
        validation_report = validate_pacifico(merged)

    if args.report:
        from pacifico_merge.utils import save_json
        report_obj = {'merge': merge_report, 'validation': validation_report}
        save_json(args.report, report_obj)

    print('Merge completado →', str(args.out))
    print('Resumen:')
    for k, v in merge_report.get('counts', {}).items():
        print(f'  - {k}: +{v.get("added", 0)} (total={v.get("total", "?")})')

    if do_validate and validation_report is not None:
        errors = validation_report.get('errors', [])
        warnings = validation_report.get('warnings', [])
        print(f'Validación: {len(errors)} errores, {len(warnings)} warnings')
        if errors and args.strict:
            print('ERROR: validación fallida en modo --strict. Revisa el reporte.', file=sys.stderr)
            return 2

    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
