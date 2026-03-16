# USER_GUIDE — merge_pacifico.py

**Audiencia:** usuarios finales / operadores del histórico `Pacifico.json`.

Esta guía explica cómo ejecutar el script, qué entradas y salidas usa, qué se fusiona y cómo verificar el resultado.

---

## 1. ¿Qué hace este script?

`merge_pacifico.py` fusiona un JSON base (histórico) con un JSON nuevo y genera un JSON combinado. La fusión se hace **por identificadores (`id`)**, evitando duplicados.

En particular:

- añade elementos de `dimensions` que no existían en el base,
- añade `results` que no existían en el base,
- integra `tree` de forma jerárquica (temporada → competición → evento → atleta).

---

## 2. Requisitos

- Python 3.x
- Los ficheros JSON deben existir en las rutas esperadas (o debes editar el script).

El script usa solo librerías estándar: `json` y `pathlib`.

---

## 3. Entradas y salidas

### 3.1 Entradas (por defecto)

El script carga siempre:

- `./JSON/Pacifico.json`  *(JSON base / histórico)*
- `./JSON/2025-2026.json` *(JSON nuevo a integrar)*

### 3.2 Salida (por defecto)

- `./JSON/Pacifico_merged.json`

> Si necesitas otras rutas/nombres, ver sección 8.

---

## 4. Ejemplo de ejecución

### 4.1 Windows PowerShell

```powershell
# 1) Ir a la carpeta del proyecto
cd C:\ruta\al\repo

# 2) Ejecutar el merge
python .\merge_pacifico.py

# 3) Verificar que se creó el fichero de salida
dir .\JSON\Pacifico_merged.json
````

Salida esperada:

```text
Merge completado → JSON/Pacifico_merged.json
```

### 4.2 Linux/macOS (zsh/bash)

```bash
# 1) Ir a la carpeta del proyecto
cd /ruta/al/repo

# 2) Ejecutar el merge
python merge_pacifico.py

# 3) Verificar que se creó el fichero de salida
ls -l ./JSON/Pacifico_merged.json
```

---

## 5. Qué se fusiona exactamente (detalle)

### 5.1 `dimensions.seasons`

*   Se indexa por `season.id`.
*   Se añaden solo temporadas cuyo `id` no exista en el JSON base.

### 5.2 `dimensions.athletes`

*   Se indexa por `athlete.id`.
*   Se añaden solo atletas cuyo `id` no exista en el JSON base.

### 5.3 `dimensions.competitions`

*   Se indexa por `competition.id`.
*   Se añaden solo competiciones cuyo `id` no exista en el JSON base.

### 5.4 `dimensions.events`

*   Se indexa por `event.id`.
*   Se añaden solo eventos cuyo `id` no exista en el JSON base.

### 5.5 `results`

*   Se indexa por `result.id`.
*   Se añaden solo resultados cuyo `id` no exista en el JSON base.

### 5.6 `tree` (jerárquico)

La fusión del árbol se hace en 4 niveles:

1.  **Season**: se busca por `season_id`.
    *   Si no existe, se añade la temporada completa.
2.  **Competition**: dentro de la temporada, se busca por `competition_id`.
    *   Si no existe, se añade la competición completa.
3.  **Event**: dentro de la competición, se busca por `event_id`.
    *   Si no existe, se añade el evento completo.
4.  **Athletes**: dentro del evento, se fusiona por `athlete_id`.
    *   Si el atleta ya existe en ese evento, no se duplica.

---

## 6. Limitaciones conocidas

1.  **No fusiona `dimensions.clubs`**
    *   Si el JSON nuevo contiene clubes no presentes en el base, no se incorporarán automáticamente.

2.  **No hay deduplicación avanzada**
    *   Solo se evita el duplicado por `id`.
    *   No se remapean entidades equivalentes con IDs distintos.

3.  **No valida el contrato JSON**
    *   Si falta alguna clave esperada, puede fallar con `KeyError`.

---

## 7. Verificación del resultado

### 7.1 Comprobar que el JSON es válido

```bash
python -c "import json; json.load(open('./JSON/Pacifico_merged.json','r',encoding='utf-8')); print('OK')"
```

### 7.2 Comprobar que hay más resultados (si aplicaba)

Puedes comparar el número de resultados antes y después:

```bash
python - << 'PY'
import json

def count_results(p):
    with open(p, 'r', encoding='utf-8') as f:
        return len(json.load(f).get('results', []))

print('Base:', count_results('./JSON/Pacifico.json'))
print('Nuevo:', count_results('./JSON/2025-2026.json'))
print('Merged:', count_results('./JSON/Pacifico_merged.json'))
PY
```

---

## 8. Cambiar rutas (opción rápida)

El script actual tiene rutas fijas. Puedes editar estas líneas:

*   Base: `pacifico = load_json("./JSON/Pacifico.json")`
*   Nuevo: `out_all = load_json("./JSON/2025-2026.json")`
*   Salida: `save_json("./JSON/Pacifico_merged.json", pacifico)`

Recomendación: mantén rutas relativas al proyecto para facilitar portabilidad.

***

## 9. Buenas prácticas

*   Haz una copia de seguridad del `Pacifico.json` antes de hacer merge.
*   Versiona el resultado (`Pacifico_merged.json`) en Git si es parte del histórico.
*   Si incorporas clubes nuevos, considera extender el script para mergear `dimensions.clubs`.

````

*(Todo este comportamiento viene directamente de `merge_pacifico.py`: rutas fijas, merge por `id`, merge jerárquico de `tree`, y la ausencia de merge de clubes.)* 
