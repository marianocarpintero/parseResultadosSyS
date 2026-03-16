# Documentación

Este directorio contiene documentación del proyecto.

## Índice

- [`README_MERGE.md`] — Resumen del Merge CLI. Este fichero.
- [`documentación/merge/USER_GUIDE.md`] — Guía de usuario (detallada)
- [`documentación/merge/TECHNICAL_NOTE.md`] — Nota técnica breve
- [`diagram_flujo_general.md`](diagram_flujo_general.md) — Diagrama de flujo general del sistema

# Merge CLI — `merge_pacifico.py`

Herramienta de línea de comandos para **fusionar (merge) dos datasets JSON** del proyecto Pacifico.

A diferencia de la versión inicial (rutas fijas), esta versión:

- acepta **argumentos CLI** (`--base`, `--new`, `--out`, etc.),
- fusiona `dimensions` incluyendo **`clubs`**,
- fusiona `tree` con **indexación** (rendimiento),
- deduplica entradas de `tree.event.athletes` por **`athlete_id + series_type + heat`**, y
- ejecuta **validación post-merge** opcional.

> Nota: `series_type` y `heat` se consideran **campos obligatorios del contrato actual** en `tree.event.athletes`. La validación los reporta como **warnings** si faltan (para compatibilidad), pero la deduplicación de `tree` asume que existen.

## Archivos

- Entry-point: `merge_pacifico.py`
- Módulos: `pacifico_merge/`

## Uso rápido

```bash
python merge_pacifico.py   --base ./JSON/Pacifico.json   --new ./JSON/2025-2026.json   --out ./JSON/Pacifico_merged.json   --report ./JSON/merge_report.json   --strict
```

## Documentación

- **Guía de usuario (completa)**: `USER_GUIDE.md`
- **Nota técnica (breve)**: `TECHNICAL_NOTE.md`
