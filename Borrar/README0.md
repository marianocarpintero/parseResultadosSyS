# pdf2json — Generador de JSON de temporada (PDF → Árbol + Results)

Este proyecto convierte **uno o varios PDFs de resultados deportivos** en un **único JSON** preparado para consumo por un frontend (dashboards, gráficas, comparativas).

El JSON generado incluye:

*   Un **árbol jerárquico**:  
    `Temporada → Competiciones → Eventos → Atletas`
*   Una lista **plana** `results[]` para gráficas y análisis temporal
*   Catálogos normalizados en `dimensions`  
    (`seasons`, `competitions`, `events`, `clubs`, `athletes`)
*   Metadatos de generación y **trazabilidad opcional** (trace JSONL)

***

## 1) Instalación

### 1.1 Requisitos

*   **Python 3.x**
*   Paquete **pdfplumber** (extracción de texto desde PDF)

### 1.2 Instalación recomendada (venv)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install pdfplumber
```

> `pdfplumber` gestiona internamente su dependencia con `pdfminer.six`.

### 1.3 Estructura de carpetas esperada

El proyecto trabaja **en rutas relativas** y crea carpetas si no existen:

```text
.
├── pdf2json.py        # entrypoint (wrapper CLI)
├── pdf2tree/             # paquete con toda la lógica
├── PDF/                  # entrada (PDFs)
└── JSON/                 # salida (JSON, trazas, dumps)
```

*   `pdf2json.py` es un wrapper que invoca el CLI real del paquete.
*   Todo el procesamiento vive en `pdf2tree/`.

***

## 2) Uso (usuario)

El CLI acepta **nombres de PDF** o **patrones (wildcards)**.  
Todos los PDFs se buscan **siempre dentro de `./PDF/`**.

Si no se pasa ningún argumento, se procesa `*.pdf`.

### 2.1 Procesar varios PDFs por patrón (modo batch recomendado)

```bash
python3 pdf2json.py "2026*.pdf"
```

También se admiten comodines genéricos:

```bash
python3 pdf2json.py "*.pdf"
```

Notas sobre resolución de entradas:

*   `2026*` → se asume `2026*.pdf`
*   `202601menores` → se asume `202601menores.pdf`

***

### 2.2 Procesar uno o varios PDFs indicando nombres

```bash
python3 pdf2json.py 202601menores.pdf 202602menores.pdf
```

> Los nombres se buscan en `./PDF/`.  
> Si no incluyen `.pdf`, el CLI añade la extensión automáticamente.

***

### 2.3 Fichero de salida (`--output`)

Por defecto:

*   `--output` = `pdf2jsontree.json`
*   Si no se indica carpeta, el fichero se guarda en `./JSON/`

Ejemplo:

```bash
python3 pdf2json.py "2026*.pdf" --output temporada_2025_2026.json
```

Resultado:

```text
./JSON/temporada_2025_2026.json
```

***

### 2.4 Debug

Activa salida detallada por consola:

```bash
python3 pdf2json.py "2026*.pdf" --debug
```

Útil para:

*   Ver PDFs resueltos
*   Diagnosticar fallos de cabecera
*   Inspeccionar parsing de eventos y atletas

***

### 2.5 Modo estricto (`--strict`)

Por defecto, si un PDF falla:

*   Se registra en `meta.source.skipped`
*   El proceso continúa

Con `--strict`, cualquier error **detiene el proceso completo**:

```bash
python3 pdf2json.py "2026*.pdf" --strict
```

***

### 2.6 Filtrado por club

Limita los resultados a clubes que contengan el texto indicado  
(se puede repetir el parámetro):

```bash
python3 pdf2json.py "2026*.pdf" \
  --club "Pacifico" \
  --club "Laguna"
```

El filtrado:

*   Se aplica durante el parsing
*   Podará automáticamente `dimensions` y `tree`

***

### 2.7 Trazabilidad (trace JSONL)

Genera un fichero **JSONL** (un evento por línea) con el detalle interno del parser:

```bash
python3 pdf2json.py "2026*.pdf" \
  --trace ./JSON/trace/trace.jsonl
```

Incluye, entre otros:

*   Página y línea del PDF
*   Tipo de token detectado
*   Estado del parser
*   Apertura/cierre de relevos
*   Emisión de clubs, atletas, eventos

Muy útil para **debug avanzado**.

***

### 2.8 Dump reproducible de `extract_text()`

Para inspeccionar exactamente qué devuelve `pdfplumber` por página:

```bash
python3 pdf2json.py "2026*.pdf" \
  --dump-text \
  --dump-text-dir ./JSON/dumps
```

Se genera un fichero `*_dump.txt` por PDF, con:

*   Separadores por página
*   Texto crudo (`extract_text()`)

***

## 3) Lógica de temporada (regla Oct–Sep)

La temporada se deriva a partir de la **fecha ISO de la competición** (`YYYY-MM-DD`):

*   **Octubre–Diciembre** → temporada termina en **año + 1**
*   **Enero–Septiembre** → temporada termina en **año**

Ejemplos:

*   `2025-10-05` → `Temporada 2025-2026`
*   `2026-03-10` → `Temporada 2025-2026`

### 3.1 Prioridad para determinar la temporada

1.  Fecha parseada de la cabecera del PDF (opción preferida)
2.  Temporada explícita en texto (`Temporada 24-25`, `2024-2025`)
3.  Fallback: `Temporada (desconocida)`

***

## 4) Normalización de datos

Centralizada en `pdf2tree/normalize.py`:

*   Normalización de espacios y guiones Unicode
*   Slugificación estable para IDs
*   Title Case controlado
*   Reordenación de nombres:
    *   `APELLIDOS, NOMBRE` → `Nombre Apellidos`
*   Conversión de tiempos:
    *   `mm:ss:cc` → `mm:ss.mmm` + segundos (float)
*   Detección de estado:
    *   `OK`, `DSQ`, `DNS`, `DNF`, `BAJA`

***

## 5) Agrupación estricta de eventos

Los eventos se identifican de forma determinista por:

**Prueba + Categoría + Sexo**

    event_id = e_<slug(prueba_base + categoría + sexo)>

### 5.1 Máster y relevos

Soporta de forma robusta:

*   `Máster 30-34`, `Máster +70`
*   `Máster R4 +170`
*   Relevos (`4x50`, `4x12,5`, Lanzamiento de Cuerda)

La distancia se detecta en cualquier parte del título (`200m`, `4x50m`, etc.).

***

## 6) Identificadores (IDs)

### 6.1 `competition_id`

Se construye como:

    c_<slug(fecha + ubicación + nombre_limpio)>

Evita colisiones entre competiciones del mismo día.

***

### 6.2 `event_id`

Basado en:

*   Prueba base
*   Categoría
*   Sexo

***

### 6.3 `club_id` y `athlete_id`

*   `club_id`
        club_<slug(nombre_club)>

*   `athlete_id` (individual)
        a_<slug(nombre)>_<año_nacimiento>

*   `athlete_id` (relevos, sin año)
        a_<slug(nombre)>_na

***

## 7) Salida: contrato JSON

Estructura raíz:

```json
{
  "meta": { ... },
  "dimensions": { ... },
  "results": [ ... ],
  "tree": [ ... ]
}
```

***

### 7.1 `meta`

Incluye:

*   `version`
*   `generated_at`
*   `timezone`
*   `source.inputs`
*   `source.inputs_resolved`
*   `source.skipped`

***

### 7.2 `dimensions`

Catálogos normalizados:

```json
{
  "seasons": [],
  "competitions": [],
  "events": [],
  "clubs": [],
  "athletes": []
}
```

***

### 7.3 `results` (vista plana)

Un registro por atleta–evento–competición, ideal para:

*   Series temporales
*   Comparativas
*   Gráficas

Incluye `time.seconds` cuando el resultado es válido.

***

### 7.4 `tree` (vista jerárquica)

*   Temporada
    *   Competiciones
        *   Eventos
            *   Atletas

Pensado para navegación directa en frontend.

***

## 8) Cómo se parsea el PDF (técnico)

1.  **Extracción por página** con `pdfplumber`
2.  **Tokenización de líneas** (`EVENT_TITLE`, `TABLE_HEADER`, `INDIVIDUAL_ROW`, etc.)
3.  **Parser single-pass** con estado explícito
4.  Gestión especial de relevos
5.  Construcción de:
    *   `dimensions`
    *   `results`
    *   `tree`

***

## 9) Troubleshooting

### 9.1 No se detectan PDFs

*   Verifica que están en `./PDF/`
*   Usa `--debug` para ver patrones resueltos

### 9.2 Fechas o cabeceras incorrectas

*   Usa `--dump-text`
*   Usa `--trace` para ver detección de cabecera

### 9.3 Problemas con relevos

*   El trace muestra aperturas/cierres de relevo
*   Se cierran automáticamente relevos inconsistentes

***

## 10) Ejemplos rápidos

### 10.1 JSON completo de temporada

```bash
python3 pdf2json.py "*.pdf" \
  --output ./JSON/temporada.json
```

### 10.2 Solo dos PDFs

```bash
python3 pdf2json.py 202601menores.pdf 202602menores.pdf \
  --output ./JSON/menores.json
```

### 10.3 Filtrado por club con trazas

```bash
python3 pdf2json.py "2026*.pdf" \
  --club "Pacifico" \
  --trace ./JSON/trace/trace.jsonl \
  --output ./JSON/pacifico_2026.json
```

***

## 11) Contrato y compatibilidad

*   `meta.version` identifica la versión del esquema
*   Cambios **aditivos** no rompen compatibilidad
*   Los consumidores deben ignorar campos desconocidos

Campos **estables**:

*   Raíz (`meta`, `dimensions`, `tree`, `results`)
*   IDs en `dimensions`
*   Claves mínimas de `results`

Campos **best‑effort**:

*   `points`, `heat`
*   `location`, `pool_type`
*   `time.raw`

***

## 12) Recomendaciones de consumo (frontend)

*   Usar `dimensions` como fuente de verdad de nombres
*   Usar IDs para joins y comparativas
*   Tratar `DSQ/DNS/DNF` como resultados sin tiempo
*   No asumir que todos los PDFs tienen fecha o puntos

***

## License

This project is licensed under the GNU Affero General Public License v3.0 (or later).
See the `LICENSE` file for details.

# Headers de ficheros .py
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