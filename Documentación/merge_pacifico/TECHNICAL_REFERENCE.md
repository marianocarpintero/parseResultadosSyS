# TECHNICAL_REFERENCE — Merge de datasets Pacifico

Documento técnico de referencia para **mantenedores y desarrolladores**. Describe el diseño, contratos, invariantes y decisiones de implementación del proceso de *merge* (`merge_pacifico.py` + `pacifico_merge/merger.py`).

> Este documento sustituye y amplía la antigua `TECHNICAL_NOTE.md`.

---

## 1. Visión general

El sistema fusiona (*merge*) dos datasets JSON del proyecto Pacifico:

- **Base / histórico**: dataset acumulado.
- **New / incremental**: dataset generado a partir de nuevos PDFs / Excels.

El merge es **no destructivo**:

- Nunca se elimina información del base.
- Solo se añaden nodos que no existían previamente.

Arquitectura por capas:

- **CLI**: `merge_pacifico.py`
- **Lógica de merge**: `pacifico_merge/merger.py`
- **Validación**: `pacifico_merge/validate.py`
- **Utilidades**: `pacifico_merge/utils.py`

Esta separación permite:

- testabilidad
- aislamiento de bugs
- evolución independiente del contrato

---

## 2. Estructura de datos (alto nivel)

El JSON final contiene cuatro bloques principales:

```text
meta
├── info de generación

dimensions
├── seasons
├── clubs
├── athletes
├── competitions
└── events

results
├── resultados planos (derivables)

tree
└── season
    └── competition
        └── event
            └── athletes[]
```

### 2.1 Rol de `tree`

- `tree` **no es derivado automáticamente** de `results`.
- Se considera una vista estructurada, optimizada para consumo UI.
- El merge de `tree` es **incremental y conservador**.

---

## 3. Merge de `dimensions`

### 3.1 Estrategia

- Merge por **`id` exacto**.
- No se modifican nodos existentes.
- Solo se añaden nuevos elementos.

Aplicable a:

- `seasons`
- `clubs`
- `athletes`
- `competitions`
- `events`

Complejidad: **O(n)** mediante indexación previa.

---

## 4. Merge de `results`

### 4.1 Estrategia

- Merge por `result.id`.
- Se asume unicidad fuerte del ID.
- No se realiza merge campo a campo.

> Cualquier conflicto de `id` es indicativo de error de generación previa.

---

## 5. Merge de `tree` (sección crítica)

### 5.1 Principios fundamentales

1. **Nunca se re-procesa un subárbol que acaba de ser copiado entero**.
2. El merge siempre avanza **de arriba hacia abajo**:
   `season → competition → event → athletes`.
3. Cada nivel decide entre:
   - *copiar nodo completo*
   - *descender y fusionar hijos*

Romper cualquiera de estos principios provoca duplicados estructurales.

---

## 5.2 Indexación

Antes del merge se construyen índices en memoria:

```text
season_idx   : season_id → season node
comp_idx     : (season_id, competition_id) → competition node
event_idx    : (season_id, competition_id, event_id) → event node
athlete_idx  : (season_id, competition_id, event_id, athlete_key)
```

Esto permite:
- evitar búsquedas lineales
- garantizar deduplicación determinista

---

## 5.3 Deduplicación de atletas (contrato)

Clave compuesta de atleta dentro de un evento:

```text
athlete_key = athlete_id + series_type + heat
```

### Reglas

- `athlete_id` → obligatorio
- `series_type` → obligatorio
- `heat` → obligatorio (puede ser `null`, pero la clave debe existir)

Si alguno de estos campos falta:
- el atleta **no entra en la deduplicación**
- la validación lo reporta como *warning*

---

## 5.4 Reglas de copia de subárboles (FIX CLAVE)

### ✅ Season nueva

Si una `season_id` no existe en base:

- se copia **toda la season**
- se indexan todas sus competitions / events / athletes
- **NO** se vuelve a recorrer su contenido

```text
append season
index subtree
continue
```

---

### ✅ Competition nueva

Si una `competition_id` no existe dentro de la season:

- se copia **toda la competition** (con todos sus events)
- se indexa el subárbol
- **NO** se vuelve a recorrer la lista de events

```text
append competition
index subtree
continue
```

---

### ✅ Event nuevo

Si un `event_id` no existe dentro de la competition:

- se copia **todo el evento** (con atletas)
- se indexan sus atletas
- **NO** se vuelve a recorrer la lista de atletas

```text
append event
index athletes
continue
```

---

### ✅ Event existente

Solo en este caso:

- se itera atleta a atleta
- se deduplica usando `athlete_key`

---

## 6. Bug histórico: “se duplica solo el primero”

### 6.1 Síntoma

- En algunos eventos aparecía duplicado **solo el primer atleta**.
- Ejemplo real:
  `e_100_m_remolque_de_maniqui_con_aletas_master_70_74_m` (Reyeros).

---

### 6.2 Causa raíz

La competición nueva se copiaba completa:

```python
pac_comps.append(out_comp)
```

pero **el código seguía descendiendo** y volvía a recorrer:

```python
for out_event in out_comp['events']:
```

Como los `event_idx` aún no estaban indexados, los eventos se añadían otra vez.

El efecto visual dependía del consumidor:
- a veces se veían eventos duplicados
- a veces solo el primer atleta parecía duplicado

---

### 6.3 Solución aplicada

- `continue` inmediato tras copiar una season/competition/event nuevo.
- Indexación explícita del subárbol recién insertado.

Este patrón está ahora **documentado y reforzado**.

---

## 7. Validación post-merge

La validación comprueba:

- Duplicados en `dimensions.*.id`
- Duplicados en `results.id`
- Referencias cruzadas (`results → dimensions`)
- Consistencia estructural del `tree`

### Severidad

- **Errores**: rompen ejecución en `--strict`.
- **Warnings**: inconsistencias toleradas (ej. `heat` ausente).

---

## 8. Invariantes garantizados tras el merge

- No existen duplicados por ID en `dimensions` ni `results`.
- En `tree`:
  - no se duplica ningún `event_id` dentro de una competition
  - no se duplica ningún atleta con la misma `athlete_key`
- El orden original del base se preserva.

---

## 9. Extensiones futuras previstas

- Endurecer contrato (`heat` obligatorio → error).
- Opción `--rebuild-tree` desde `results`.
- Tests unitarios específicos:
  - season nueva
  - competition nueva
  - event nuevo
  - atleta duplicado
- Métricas de merge (tiempos, tamaños).

---

## 10. Reglas de oro para tocar `merger.py`

1. **Si copias un nodo entero → `continue` inmediato**.
2. **Indexa siempre lo que acabas de insertar**.
3. Nunca mezclar:
   - copia estructural
   - merge incremental
   en el mismo nivel.

Si una modificación rompe una de estas reglas, el resultado será incorrecto.

---

**Estado del documento**: actualizado tras fix definitivo de duplicados en `tree` (marzo 2026).
