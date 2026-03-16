# merge_pacifico.py

Herramienta para **fusionar (merge) datasets JSON** del proyecto Pacifico.

Este script toma un JSON base (histórico) y un JSON nuevo (p. ej. una temporada recién generada) y produce un JSON combinado **sin duplicar** elementos ya existentes (por `id`).

> Nota: el script actual usa **rutas fijas** (hardcodeadas). Si tus ficheros están en otra ubicación o tienen otro nombre, consulta la guía de usuario.

## ¿Qué fusiona?

- `dimensions.seasons`
- `dimensions.athletes`
- `dimensions.competitions`
- `dimensions.events`
- `results`
- `tree` (merge jerárquico por `season_id → competition_id → event_id → athlete_id`)

## ¿Qué NO fusiona? (limitación actual)

- `dimensions.clubs` (no hay bloque de merge para clubes)

## Uso rápido

```bash
python merge_pacifico.py
```

Entradas/salida por defecto:

*   Base: `./JSON/Pacifico.json`
*   Nuevo: `./JSON/2025-2026.json`
*   Salida: `./JSON/Pacifico_merged.json`
