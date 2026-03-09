# pdf2tree.py — Generador de JSON de temporada (PDF → Árbol + Results)

Este script convierte **uno o varios PDFs de resultados** en un **único JSON** preparado para un frontend (dashboard). El JSON resultante incluye: 

- Un **árbol jerárquico**: `Temporada → Competiciones → Eventos → Atletas`   
- Una lista **plana** `results[]` para gráficos/comparativas   
- Catálogos en `dimensions` (seasons/clubs/athletes/competitions/events)   
- Metadatos de trazabilidad (`invocation`, `glob`, `inputs_resolved`, `skipped`, `inputs_fingerprint`)   

---

## 1) Instalación

### 1.1 Requisitos
- **Python 3.x**   
- Paquete **pdfplumber**   

### 1.2 Instalación recomendada (venv)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install pdfplumber
```

`pdfplumber` depende internamente de `pdfminer.six`. El `pip install pdfplumber` lo gestiona. 

### 1.3 Estructura de carpetas esperada

El script trabaja **en rutas relativas** y crea carpetas si no existen: 

```text
.
├── pdf2tree.py
├── PDF/     # entrada (PDFs)
└── JSON/    # salida (JSON)
```

***

## 2) Uso (usuario)

### 2.1 Procesar varios PDFs con `--glob` (modo batch recomendado)

Procesa todos los PDFs que cumplan el patrón dentro de `./PDF/`: 

```bash
python3 pdf2tree.py --glob "2026*.pdf"
```

Si no indicas `--output`, el nombre por defecto se deriva del patrón:

*   `--glob "2026*.pdf"` → `./JSON/2026_tree.json` 

### 2.2 Procesar uno o varios PDFs indicando nombres

```bash
python3 pdf2tree.py 202601menores.pdf 202602menores.pdf
```

> Los nombres se buscan en `./PDF/`. Si no incluyen `.pdf`, el script la añade. 

### 2.3 Debug

Activa trazas de depuración (eventos, líneas candidatas, participantes parseados): 

```bash
python3 pdf2tree.py --glob "2026*.pdf" --debug
```

### 2.4 Filtrar por club

Puedes limitar los resultados a clubes que contengan el texto indicado (se puede repetir): 

```bash
python3 pdf2tree.py --glob "2026*.pdf" --club-filter "Pacifico"
```

***

## 3) Lógica de temporada (regla Oct–Sep)

La temporada se deriva **exclusivamente** de la fecha ISO de competición (`YYYY-MM-DD`) aplicando: 

*   **Octubre–Diciembre** → la temporada “termina” en **año + 1** 
*   **Enero–Septiembre** → la temporada “termina” en **año** 

Ejemplos:

*   `2025-10-05` → temporada fin `2026` → `Temporada 2025-2026` 
*   `2026-03-10` → temporada fin `2026` → `Temporada 2025-2026` 

### 3.1 Validación por `--glob`

En modo `--glob`, el script extrae el año inicial del patrón (p.ej. `2026*.pdf`) y lo considera **temporada esperada (end\_year)**. Si la fecha de un PDF produce una temporada distinta, ese PDF se **avisa y se salta**: 

*   `SKIP (sin fecha válida)` si no se pudo parsear fecha 
*   `SKIP (temporada por fecha X != esperada Y)` si el cálculo por fecha no coincide con el año del `--glob` 

***

## 4) Limpieza del nombre de competición

El script incluye `limpiar_competicion()` para mejorar visualización y evitar ruido: 

*   Elimina `Fase Territorial` (case-insensitive) incluso si aparece rodeado de guiones 
*   Normaliza guiones `-`, `–`, `—`, etc. a un separador uniforme `–` 
*   Compacta espacios y elimina separadores sobrantes en extremos 

El resultado se guarda como `name_clean`. 

***

## 5) Agrupación estricta de eventos (comparativas)

Los eventos se agrupan por: **Prueba + Sexo + Categoría** (estricto). 

### 5.1 Máster con rangos y “+70”

Para Máster, la categoría puede incluir: 

*   `Máster 30-39`, `Máster 40-49`, …
*   `Máster +70`

Esto se detecta desde la línea de evento, y pasa a formar parte del `event_id`. 

***

## 6) Identificadores (IDs) y colisiones

### 6.1 `competition_id` (evita colisiones Menores/Máster)

El `competition_id` se construye incorporando:

*   fecha (`date_iso`) + lugar (`location`) + **nombre limpio** (`competition_name_clean`) 

Esto evita colisiones cuando dos PDFs tienen misma fecha y piscina, pero nombres distintos. 

### 6.2 `event_id`

Se compone de:

*   `prueba_base`, `category`, `sex` (slugificados) 

### 6.3 `athlete_id` y `club_id`

*   `athlete_id`: nombre normalizado + año de nacimiento 
*   `club_id`: slug del nombre del club 

***

## 7) Salida: contrato JSON (explicación de **cada campo**)

La salida final tiene esta estructura raíz: 

```json
{
  "meta": {...},
  "dimensions": {...},
  "tree": [...],
  "results": [...]
}
```

A continuación se explica **campo por campo**.

***

### 7.1 `meta` (metadatos)

```json
"meta": {
  "version": "1.1.0",
  "generated_at": "ISO-8601 con zona horaria",
  "timezone": "Europe/Madrid",
  "source": {...},
  "season_rule": "...",
  "season_end_year": 2026
}
```

*   **`version`**: versión del “formato” de salida que marca el script. 
*   **`generated_at`**: fecha/hora de generación en ISO local con zona. 
*   **`timezone`**: zona horaria usada (fijada en el script). 
*   **`source`**: bloque de trazabilidad (ver 7.1.1). 
*   **`season_rule`**: texto descriptivo de la regla de temporada (“Oct-01..Sep-30 => season\_end\_year”). 
*   **`season_end_year`**: temporada “esperada” tomada del año del glob (si se usó `--glob`). Puede ser `null` si no se usó glob. 

#### 7.1.1 `meta.source` (trazabilidad)

```json
"source": {
  "file": "un_pdf_individual.pdf",
  "generator": "pdf2tree.py (multi-pdf merge)",
  "invocation": "python3 ... --glob \"2026*.pdf\" ...",
  "glob": "2026*.pdf",
  "inputs_resolved": ["...pdf", "...pdf"],
  "skipped": [{"file":"...pdf", "reason":"..."}],
  "inputs_fingerprint": "a1b2c3d4e5f6"
}
```

*   **`file`**: en bundles individuales es el PDF procesado; en merge puede quedar el del primero. 
*   **`generator`**: nombre del script; en merge se marca como multi-pdf. 
*   **`invocation`**: comando exacto ejecutado (tal cual `sys.argv`). 
*   **`glob`**: patrón `--glob` usado (o `null`). 
*   **`inputs_resolved`**: lista de PDFs **realmente incluidos** (los que pasaron validaciones). 
*   **`skipped`**: lista de PDFs omitidos con el motivo (`sin fecha válida`, `temporada distinta`, `error parseando`). 
*   **`inputs_fingerprint`**: hash corto del conjunto de PDFs incluidos (sirve para detectar cambios del dataset). 

***

### 7.2 `dimensions` (catálogos)

```json
"dimensions": {
  "seasons": [...],
  "clubs": [...],
  "athletes": [...],
  "competitions": [...],
  "events": [...]
}
```

Los arrays actúan como tablas de referencia para evitar repetir strings en toda la salida. 

#### 7.2.1 `dimensions.seasons[]`

```json
{ "id": "s_2025_2026", "label": "Temporada 2025-2026" }
```

*   **`id`**: identificador determinista basado en el label (slug). 
*   **`label`**: etiqueta humana “Temporada AAAA-AAAA”. 

#### 7.2.2 `dimensions.clubs[]`

```json
{ "id": "club_cn_pacifico", "name": "C.N. Pacífico", "slug": "cn_pacifico" }
```

*   **`id`**: `club_` + slug. 
*   **`name`**: texto del club tal cual aparece en PDF. 
*   **`slug`**: versión normalizada para URLs/keys. 

#### 7.2.3 `dimensions.athletes[]`

```json
{ "id": "a_maria_gomez_2004", "name": "María Gómez", "birth_year": 2004 }
```

*   **`id`**: `a_` + slug(nombre) + `_` + año nacimiento. 
*   **`name`**: nombre normalizado (reordena “APELLIDOS, NOMBRE” si aplica). 
*   **`birth_year`**: año capturado de la línea de atleta. 

#### 7.2.4 `dimensions.competitions[]`

```json
{
  "id": "c_...",
  "season_id": "s_...",
  "date": "YYYY-MM-DD",
  "name": "Nombre original",
  "name_clean": "Nombre limpio (sin 'Fase Territorial')",
  "location": "Piscina / sede",
  "region": "Madrid",
  "pool_type": ""
}
```

*   **`id`**: determinista a partir de `date + location + name_clean`. 
*   **`season_id`**: referencia a la temporada. 
*   **`date`**: fecha ISO si se pudo parsear; si no, puede ser cadena vacía. 
*   **`name`**: nombre original extraído del PDF. 
*   **`name_clean`**: nombre limpio (quita “Fase Territorial” y normaliza guiones). 
*   **`location`**: lugar/piscina extraído. 
*   **`region`**: comunidad (fijada a “Madrid” en el extractor actual). 
*   **`pool_type`**: campo reservado (por ahora vacío). 

#### 7.2.5 `dimensions.events[]`

```json
{
  "id": "e_...",
  "base": "100 m. Socorrista",
  "sex": "F|M|X",
  "category": "Máster 40-49 | Absoluto | ...",
  "distance_m": 100,
  "discipline": "texto de prueba_base"
}
```

*   **`id`**: determinista por `prueba_base + category + sex`. 
*   **`base`**: nombre de prueba sin sexo/categoría. 
*   **`sex`**: `F`, `M` o `X` (Mixto) inferido del encabezado de evento. 
*   **`category`**: incluye rangos Máster si existen. 
*   **`distance_m`**: distancia inferida desde `prueba_base` si empieza por número. 
*   **`discipline`**: actualmente igual a `prueba_base` (campo reservado por si en el futuro se separa disciplina). 

***

### 7.3 `tree` (vista jerárquica)

`tree` es un array con un único elemento (una temporada), que contiene las competiciones. 

```json
"tree": [
  {
    "season_id": "...",
    "season_label": "...",
    "competitions": [...]
  }
]
```

#### 7.3.1 `tree[].competitions[]`

```json
{
  "competition_id": "...",
  "season_id": "...",
  "date": "YYYY-MM-DD",
  "name": "...",
  "name_clean": "...",
  "location": "...",
  "region": "...",
  "pool_type": "",
  "events": [...]
}
```

*   Los eventos se ordenan por: distancia, prueba base, (Máster ordenado por rango), categoría, sexo. 

#### 7.3.2 `tree[].competitions[].events[]`

```json
{
  "event_id": "...",
  "base": "...",
  "sex": "F|M|X",
  "category": "...",
  "athletes": [...]
}
```

#### 7.3.3 `tree[].competitions[].events[].athletes[]`

```json
{
  "athlete_id": "...",
  "club_id": "...",
  "status": "OK|DSQ",
  "position": 3,
  "points": null,
  "time": {
    "display": "01:23.450|DSQ",
    "seconds": 83.45|null,
    "raw": "1:23:45|Descalificado"
  }
}
```

*   **`status`**: `OK` para tiempos válidos o `DSQ` si “Descalificado”. 
*   Los atletas se ordenan dejando los `OK` primero por tiempo y los `DSQ` al final. 

***

### 7.4 `results` (vista plana para gráficos)

`results` contiene un registro por atleta-evento-competición, y se ordena por fecha en el resultado final. 

```json
{
  "id": "r_...",
  "date": "YYYY-MM-DD",
  "season_id": "...",
  "competition_id": "...",
  "event_id": "...",
  "athlete_id": "...",
  "club_id": "...",
  "time": {...},
  "status": "OK|DSQ",
  "position": 3,
  "points": null,
  "labels": {
    "x": "YYYY-MM-DD\nNombre competición"
  }
}
```

*   **`labels.x`**: etiqueta simple para eje X (fecha + nombre). 
*   **`time.seconds`**: `null` en DSQ; numérico en OK (segundos float). 

***

## 8) Cómo se parsea el PDF (técnico)

### 8.1 Reconstrucción de líneas

Se extraen palabras con `pdfplumber.extract_words(...)` y se reagrupan por coordenada vertical (`top`) para recomponer líneas. 

### 8.2 Cabecera de competición

Se busca una página que contenga `RESULTADOS DEFINITIVOS` y se toma: 

*   línea siguiente → nombre competición
*   línea posterior → fecha/lugar  
    Además se intenta parsear fechas tipo “13 de Abril 2024”. 

### 8.3 Parsing de atletas

Primero se intenta tokenizar (`parse_athlete_line`) buscando: posición, año, tiempo/Descalificado; si falla, se usa `ATHLETE_RE` como fallback. 

***

## 9) Troubleshooting

### 9.1 “No aparecen algunos PDFs al usar --glob”

Revisa la salida:

*   `SKIP (sin fecha válida)` o
*   `SKIP (temporada por fecha X != esperada Y)` 

y consulta `meta.source.skipped` en el JSON final. 

### 9.2 “Menores y Máster se mezclan”

Esto se evita usando `competition_id` = `date + location + competition_name_clean`. Si aún ocurriera, revisa que el nombre limpio sea distinto (p.ej. “Máster …” vs “Menores …”). 

***

## 10) Ejemplos rápidos

### 10.1 Generar JSON de temporada 2025-2026

```bash
python3 pdf2tree.py --glob "2026*.pdf" --output "./JSON/temporada_2025_2026.json"
```

### 10.2 Generar JSON solo para dos PDFs concretos

```bash
python3 pdf2tree.py 202601menores.pdf 202602menores.pdf --output "./JSON/menores.json"
```

***

## 11) Notas y mejoras sugeridas (sin cambiar el contrato)

*   Estabilizar `results.id` construyendo `res_key` con un separador explícito (p.ej. `|`) para evitar dependencias de “continuaciones” de línea. 
*   Estabilizar `inputs_fingerprint` usando un separador explícito (p.ej. `|`) en lugar de una cadena con `\` continuado. 
*   Considerar derivar `expected_end_year` del primer PDF válido en `--glob` (en lugar de extraerlo del patrón) si el naming no es totalmente fiable. 

***

## 12) Contrato (compatibilidad y estabilidad del JSON)

Esta sección define el **contrato de datos** entre el generador (`pdf2tree.py`) y el frontend/consumidores del JSON. Se distingue entre campos **estables** (compatibilidad garantizada salvo bump de versión) y campos **best‑effort** (pueden variar por cambios de PDF, mejoras del parser o disponibilidad de información). 

### 12.1 Versionado y compatibilidad

- `meta.version` identifica la **versión del esquema** de salida. Cambios incompatibles deben acompañarse de un incremento de versión (idealmente mayor/menor, según política).   
- El consumidor debe:
  - Leer `meta.version` y asumir compatibilidad si solo cambian campos **aditivos** (se agregan nuevos campos manteniendo los existentes).   
  - Tratar campos desconocidos como “ignorar si no se necesitan” (forward‑compatibility).   

> Recomendación: el frontend debe depender principalmente de IDs + `dimensions` y no de textos de origen, para maximizar estabilidad.   

---

### 12.2 Campos **estables** (contrato fuerte)

#### Raíz del documento
- `meta` (objeto) — siempre presente.   
- `dimensions` (objeto) — siempre presente con claves: `seasons`, `clubs`, `athletes`, `competitions`, `events`.   
- `tree` (array) — siempre presente; en el diseño actual contiene **una temporada** en `tree[0]`.   
- `results` (array) — siempre presente; lista plana para gráficas/comparativas.   

#### Meta
- `meta.version` (string) — versión del esquema.   
- `meta.generated_at` (string ISO) — timestamp de generación.   
- `meta.timezone` (string) — zona horaria (actualmente “Europe/Madrid”).   
- `meta.source.invocation` (string) — comando exacto ejecutado (trazabilidad).   
- `meta.source.inputs_resolved` (array de strings) — lista final de PDFs incluidos.   
- `meta.source.skipped` (array) — lista de PDFs omitidos con motivo.   
- `meta.source.inputs_fingerprint` (string) — huella del set de entrada (hash corto).   

#### Dimensions (IDs y claves)
- Cada elemento en `dimensions.*[]` contiene como mínimo `id` (string).   
- `dimensions.seasons[]`: `id`, `label`.   
- `dimensions.clubs[]`: `id`, `name`, `slug`.   
- `dimensions.athletes[]`: `id`, `name`, `birth_year`.   
- `dimensions.competitions[]`: `id`, `season_id`, `date`, `name`, `name_clean`, `location`, `region`, `pool_type`.   
- `dimensions.events[]`: `id`, `base`, `sex`, `category`, `distance_m`, `discipline`.   

#### Tree (estructura jerárquica)
- `tree[0].season_id` y `tree[0].season_label`.   
- `tree[0].competitions[]` con `competition_id` y `events[]`.   
- `events[]` con `event_id` y `athletes[]`.   
- `athletes[]` con `athlete_id`, `club_id`, `status`, `time`.   

#### Results (vista plana)
Cada entrada de `results[]` incluye como mínimo:
- `id`, `date`, `season_id`, `competition_id`, `event_id`, `athlete_id`, `club_id`, `time`, `status`, `labels.x`.   

---

### 12.3 Campos **best‑effort** (contrato débil)

Estos campos dependen del formato del PDF o de que la información exista y sea parseable:

- `dimensions.competitions[].date`: puede ser vacío si no se pudo parsear fecha.   
- `dimensions.competitions[].location`: puede ser vacío si no se pudo extraer lugar.   
- `dimensions.competitions[].pool_type`: actualmente se deja vacío (campo reservado).   
- `results[].points`: opcional; depende de si existe en el PDF.   
- `results[].position`: opcional; depende del parseo de la línea.   
- `time.raw`: refleja el token de tiempo o texto (“Descalificado”) tal como aparece.   
- `time.display`: para tiempos se deriva de `mm:ss:cc → mm:ss.mmm`; para DSQ se fija a “DSQ”.   

---

### 12.4 Semántica de `status` y tiempos

- `status="OK"` ⇒ `time.seconds` es numérico (float) y `time.display` es `mm:ss.mmm`.   
- `status="DSQ"` ⇒ `time.seconds=null` y `time.display="DSQ"`.   

El frontend debe:
- Dibujar `OK` como puntos/series con `time.seconds`.   
- Representar `DSQ` como marcador especial (p.ej. un símbolo distinto o una banda inferior) sin necesidad de valor numérico.   

---

### 12.5 Garantía de orden

- `results[]` se ordena por `date` ascendente al final del proceso.   
- Dentro de cada `event`, los atletas se ordenan poniendo primero tiempos válidos (OK) y DSQ al final.   

> Nota: si `date` es vacío, esos registros pueden ir al final por el criterio de ordenación.   

***

## 13) Ejemplos anonimizados (JSON)

Los siguientes ejemplos son **anonimizados** (nombres y clubes ficticios) pero reflejan fielmente la estructura y campos generados por el script.   

### 13.1 Ejemplo: `meta` + `dimensions` (fragmento)

```json
{
  "meta": {
    "version": "1.1.0",
    "generated_at": "2026-02-26T12:53:47+01:00",
    "timezone": "Europe/Madrid",
    "source": {
      "file": "202601_master.pdf",
      "generator": "pdf2tree.py (multi-pdf merge)",
      "invocation": "python3 pdf2tree.py --glob \"2026*.pdf\" --output ./JSON/2026_tree.json",
      "glob": "2026*.pdf",
      "inputs_resolved": [
        "202601_master.pdf",
        "202601_menores.pdf",
        "202602_menores.pdf"
      ],
      "skipped": [
        { "file": "202699_raro.pdf", "reason": "sin fecha válida" }
      ],
      "inputs_fingerprint": "a1b2c3d4e5f6"
    },
    "season_rule": "Oct-01..Sep-30 => season_end_year",
    "season_end_year": 2026
  },
  "dimensions": {
    "seasons": [
      { "id": "s_2025_2026", "label": "Temporada 2025-2026" }
    ],
    "clubs": [
      { "id": "club_club_laguna_sos", "name": "Club Laguna SOS", "slug": "club_laguna_sos" },
      { "id": "club_cde_master_arganda", "name": "C.D.E Máster Arganda", "slug": "cde_master_arganda" }
    ],
    "athletes": [
      { "id": "a_atleta_uno_2008", "name": "Atleta Uno", "birth_year": 2008 },
      { "id": "a_atleta_dos_1993", "name": "Atleta Dos", "birth_year": 1993 }
    ],
    "competitions": [
      {
        "id": "c_2026_01_15_cdm_piscina_madrid_master",
        "season_id": "s_2025_2026",
        "date": "2026-01-15",
        "name": "Campeonato – Máster – Fase Territorial – Madrid",
        "name_clean": "Campeonato – Máster – Madrid",
        "location": "C.D.M. Piscina Madrid",
        "region": "Madrid",
        "pool_type": ""
      },
      {
        "id": "c_2026_01_15_cdm_piscina_madrid_menores",
        "season_id": "s_2025_2026",
        "date": "2026-01-15",
        "name": "Campeonato – Menores – Fase Territorial – Madrid",
        "name_clean": "Campeonato – Menores – Madrid",
        "location": "C.D.M. Piscina Madrid",
        "region": "Madrid",
        "pool_type": ""
      }
    ],
    "events": [
      {
        "id": "e_100_m_remolque_de_maniqui_con_aletas_master_30_39_f",
        "base": "100 m. Remolque de Maniquí con Aletas",
        "sex": "F",
        "category": "Máster 30-39",
        "distance_m": 100,
        "discipline": "100 m. Remolque de Maniquí con Aletas"
      }
    ]
  }
}
```

**Notas del ejemplo**:

*   `name_clean` elimina “Fase Territorial” y normaliza guiones. 
*   Dos competiciones distintas (`Máster` y `Menores`) comparten fecha y piscina pero tienen IDs distintos por incluir `name_clean`. 

***

### 13.2 Ejemplo: `tree` (Temporada → Competiciones → Eventos → Atletas)

```json
{
  "tree": [
    {
      "season_id": "s_2025_2026",
      "season_label": "Temporada 2025-2026",
      "competitions": [
        {
          "competition_id": "c_2026_01_15_cdm_piscina_madrid_master",
          "season_id": "s_2025_2026",
          "date": "2026-01-15",
          "name": "Campeonato – Máster – Fase Territorial – Madrid",
          "name_clean": "Campeonato – Máster – Madrid",
          "location": "C.D.M. Piscina Madrid",
          "region": "Madrid",
          "pool_type": "",
          "events": [
            {
              "event_id": "e_100_m_remolque_de_maniqui_con_aletas_master_30_39_f",
              "base": "100 m. Remolque de Maniquí con Aletas",
              "sex": "F",
              "category": "Máster 30-39",
              "athletes": [
                {
                  "athlete_id": "a_atleta_dos_1993",
                  "club_id": "club_club_laguna_sos",
                  "status": "DSQ",
                  "position": 3,
                  "points": null,
                  "time": {
                    "display": "DSQ",
                    "seconds": null,
                    "raw": "Descalificado"
                  }
                },
                {
                  "athlete_id": "a_atleta_tres_1990",
                  "club_id": "club_cde_master_arganda",
                  "status": "OK",
                  "position": 1,
                  "points": null,
                  "time": {
                    "display": "01:12.340",
                    "seconds": 72.34,
                    "raw": "1:12:34"
                  }
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

**Notas del ejemplo**:

*   `DSQ` aparece como atleta con `time.seconds=null` y `status="DSQ"`. 
*   El orden dentro de `athletes[]` puede mostrar primero OK por tiempo y DSQ al final (según el criterio de ordenación). 

***

### 13.3 Ejemplo: `results` (vista plana para gráficos)

```json
{
  "results": [
    {
      "id": "r_2026_01_15_c_2026_01_15_cdm_piscina_madrid_master_e_100_m_remolque_de_maniqui_con_aletas_master_30_39_f_a_atleta_tres_1990",
      "date": "2026-01-15",
      "season_id": "s_2025_2026",
      "competition_id": "c_2026_01_15_cdm_piscina_madrid_master",
      "event_id": "e_100_m_remolque_de_maniqui_con_aletas_master_30_39_f",
      "athlete_id": "a_atleta_tres_1990",
      "club_id": "club_cde_master_arganda",
      "time": { "display": "01:12.340", "seconds": 72.34, "raw": "1:12:34" },
      "status": "OK",
      "position": 1,
      "points": null,
      "labels": { "x": "2026-01-15\nCampeonato – Máster – Fase Territorial – Madrid" }
    },
    {
      "id": "r_2026_01_15_c_2026_01_15_cdm_piscina_madrid_master_e_100_m_remolque_de_maniqui_con_aletas_master_30_39_f_a_atleta_dos_1993",
      "date": "2026-01-15",
      "season_id": "s_2025_2026",
      "competition_id": "c_2026_01_15_cdm_piscina_madrid_master",
      "event_id": "e_100_m_remolque_de_maniqui_con_aletas_master_30_39_f",
      "athlete_id": "a_atleta_dos_1993",
      "club_id": "club_club_laguna_sos",
      "time": { "display": "DSQ", "seconds": null, "raw": "Descalificado" },
      "status": "DSQ",
      "position": 3,
      "points": null,
      "labels": { "x": "2026-01-15\nCampeonato – Máster – Fase Territorial – Madrid" }
    }
  ]
}
```

**Uso típico en frontend**:

*   Gráfica de evolución: filtrar por `event_id` + lista de `athlete_id`, ordenar por `date`, usar `time.seconds`. 
*   Puntos DSQ: filtrar `status=="DSQ"` y dibujar marcadores especiales (sin `seconds`). 

***

## 14) Recomendaciones de consumo (frontend)

*   Usar `dimensions` como fuente de verdad de nombres (clubes, atletas, competiciones, eventos). 
*   Tratar `name` como “texto original” y `name_clean` como “texto de UI”. 
*   No asumir que `points` existe; tratarlo como opcional. 
*   No asumir que `date` siempre existe en PDFs individuales; en batch se omiten los PDFs sin fecha válida. 

