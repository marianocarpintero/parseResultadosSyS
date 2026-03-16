# TECHNICAL_NOTE — merge_pacifico.py

Documento técnico breve para mantenedores.

---

## 1. Resumen del algoritmo

1. Carga el JSON base (`Pacifico.json`) y el JSON nuevo (`2025-2026.json`).
2. Para cada colección en `dimensions` (`seasons`, `athletes`, `competitions`, `events`):
   - indexa por `id` (diccionario `{id: item}`)
   - añade elementos no existentes.
3. Para `results`:
   - indexa por `result.id`
   - añade resultados no existentes.
4. Para `tree`:
   - merge jerárquico por `season_id → competition_id → event_id → athlete_id`.
5. Escribe `Pacifico_merged.json` con `ensure_ascii=False` e indentación `2`.

---

## 2. Complejidad

- El merge de listas por índice es O(n) por colección.
- El merge de `tree` usa búsquedas lineales por nivel; en árboles grandes puede crecer a O(n²) por temporada/competición.

> Si el árbol crece mucho, convendría indexar también `tree` para evitar búsquedas lineales.

---

## 3. Limitaciones actuales

- No se fusiona `dimensions.clubs`.
- No se valida la consistencia cruzada entre `dimensions`, `results` y `tree`.
- No hay remapeo de atletas (solo dedup por `id`).

---

## 4. Extensiones recomendadas (futuras)

- Añadir soporte de CLI (`argparse`) para pasar rutas (`--base`, `--new`, `--out`).
- Merge de `dimensions.clubs`.
- Indexación de `tree` por temporada/competición/evento para rendimiento.
- Validación opcional post-merge (referencias cruzadas).
````

*(De nuevo: describe el algoritmo real del script.)*
