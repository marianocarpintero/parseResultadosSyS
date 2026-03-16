# USER_GUIDE — Merge CLI (`merge_pacifico.py`)

**Audiencia:** operadores / mantenedores del histórico `Pacifico.json`.

Esta guía explica:

- cómo ejecutar el merge con argumentos,
- qué se fusiona y cómo,
- cómo validar el resultado y generar informes,
- troubleshooting y buenas prácticas.

---

## 1. ¿Qué hace esta herramienta?

`merge_pacifico.py` fusiona dos JSONs compatibles con el contrato Pacifico:

- **base**: histórico/canónico (p. ej. `Pacifico.json`)
- **new**: lote nuevo a integrar (p. ej. una temporada `2025-2026.json`)

El resultado se escribe en un fichero de salida (`--out`).

La fusión evita duplicados por ID en:

- `dimensions` (`seasons`, `clubs`, `athletes`, `competitions`, `events`)
- `results`

Y además fusiona el bloque `tree` (si no se desactiva) con deduplicación por atleta + serie + heat.

---

## 2. Requisitos

- Python 3.x
- Archivos JSON válidos (UTF-8)
- Estructura base compatible con el contrato (al menos: `meta`, `dimensions`, `results`)

No requiere dependencias externas.

---

## 3. Argumentos CLI

### 3.1 Obligatorios

- `--base`  Ruta al JSON base/histórico.
- `--new`   Ruta al JSON nuevo a integrar.
- `--out`   Ruta del JSON resultante.

Ejemplo:

```bash
python merge_pacifico.py --base ./JSON/Pacifico.json --new ./JSON/2025-2026.json --out ./JSON/Pacifico_merged.json
```

### 3.2 Opcionales

- `--report <ruta>`
  - Guarda un informe JSON con contadores de merge y resultados de validación.

- `--strict`
  - Si la validación genera errores, el proceso termina con exit code != 0.

- `--no-merge-tree`
  - Omite el merge del bloque `tree` (fusiona solo `dimensions` + `results`).

- Validación:
  - Por defecto la validación está activa.
  - `--no-validate` desactiva la validación post-merge.

---

## 4. Ejemplos de ejecución

### 4.1 Ejecución típica (recomendada)

```bash
python merge_pacifico.py   --base ./JSON/Pacifico.json   --new ./JSON/2025-2026.json   --out ./JSON/Pacifico_merged.json   --report ./JSON/merge_report.json   --strict
```

Salida esperada (resumen):

- Se imprime `Merge completado → <out>`
- Se imprime un resumen `+added` por cada dimensión y `results`
- Se imprime el número de errores/warnings de validación

### 4.2 Sin merge de `tree`

```bash
python merge_pacifico.py   --base ./JSON/Pacifico.json   --new ./JSON/2025-2026.json   --out ./JSON/Pacifico_merged.json   --no-merge-tree
```

### 4.3 Sin validación

```bash
python merge_pacifico.py   --base ./JSON/Pacifico.json   --new ./JSON/2025-2026.json   --out ./JSON/Pacifico_merged.json   --no-validate
```

---

## 5. Qué se fusiona (detalle)

### 5.1 Merge de `dimensions` (por `id`)

Se fusionan estas listas dentro de `dimensions`:

- `seasons`
- `clubs`
- `athletes`
- `competitions`
- `events`

Regla:
- se crea un índice por `id` en el JSON base
- se añaden los elementos del JSON nuevo cuyo `id` no exista en el base

### 5.2 Merge de `results` (por `result.id`)

Regla:
- se indexa `results` del base por `id`
- se añaden resultados del nuevo cuyo `id` no exista

### 5.3 Merge de `tree` (si está activado)

El `tree` se fusiona jerárquicamente:

1. `season_id`
2. `competition_id`
3. `event_id`
4. `athletes[]`

#### Deduplicación dentro de `tree.event.athletes`

Para evitar colisiones entre series/mangas, la deduplicación usa la clave:

- `athlete_id + series_type + heat`

En particular:

- `series_type` **debe existir** (contrato actual)
- `heat` **debe existir** (puede ser `null`, pero la clave debe existir)

> Si faltan, la validación lo reporta como **warning** para compatibilidad.

---

## 6. Validación post-merge

Si la validación está activa, se comprueban:

### 6.1 Estructura mínima

- Existen claves top-level: `meta`, `dimensions`, `results`.

### 6.2 Duplicados

- IDs duplicados en `dimensions.*`.
- IDs duplicados en `results`.

### 6.3 Referencias cruzadas (`results` → `dimensions`)

Para cada `result` se valida que existan en `dimensions`:

- `season_id` → `dimensions.seasons`
- `competition_id` → `dimensions.competitions`
- `event_id` → `dimensions.events`
- `athlete_id` → `dimensions.athletes`
- `club_id` → `dimensions.clubs`

### 6.4 Referencias en `tree` (warnings)

Se reporta como warning si en `tree` aparece un id que no existe en `dimensions`.
Además, se reporta como warning si un atleta en `tree.event.athletes` no contiene:

- `series_type`
- `heat`

---

## 7. Troubleshooting

### 7.1 FileNotFoundError

- Comprueba rutas en `--base`, `--new`, `--out`.
- Asegúrate de ejecutar desde la raíz del repo (o usa rutas absolutas).

### 7.2 Errores de validación con `--strict`

- Revisa el informe `--report`.
- Corrige IDs inexistentes o duplicados en el JSON de entrada.

### 7.3 No se fusiona `tree`

- Verifica que no usas `--no-merge-tree`.

---

## 8. Buenas prácticas

- Haz backup de tu base antes de aplicar merge.
- Genera siempre un `--report` para auditoría.
- Usa `--strict` en pipelines automáticos.
- Si el histórico crece mucho, mantén `tree` consistente (es vista de UI), y usa `results` para análisis.
