# JSON\_CONTRACT.md

## Especificación del contrato JSON

**Proyecto**: Pacifico – Resultados deportivos estructurados  
**Audiencia**: Desarrolladores, integradores, analistas técnicos  
**Propósito**: Definir el formato y significado del JSON generado  
**Versión del documento**: 1.0.1  
**Versión del contrato**: Ver campo `meta.version`

***

## 1. Visión general

El fichero JSON generado por el proyecto sigue un **modelo relacional normalizado**, organizado en cuatro bloques principales:

```json
{
  "meta": { ... },
  "dimensions": { ... },
  "results": [ ... ],
  "tree": [ ... ]
}
```

Principios del contrato:

*   los identificadores (`id`) son **únicos y estables**,
*   las relaciones se hacen **por referencia**, no por duplicación,
*   el contrato es **versionable y extensible**,
*   los campos opcionales pueden ser `null`.

***

## 2. `meta`

### Propósito

Contiene metadatos sobre **cómo y cuándo** se ha generado el fichero.

### Estructura

```json
"meta": {
  "version": "1.1.0",
  "generated_at": "2026-03-12T20:08:29+01:00",
  "timezone": "Europe/Madrid",
  "source": { ... }
}
```

### Campos

| Campo          | Tipo              | Obligatorio | Descripción               |
| -------------- | ----------------- | ----------- | ------------------------- |
| `version`      | string            | ✅           | Versión del contrato JSON |
| `generated_at` | string (ISO‑8601) | ✅           | Fecha/hora de generación  |
| `timezone`     | string            | ✅           | Zona horaria usada        |
| `source`       | object            | ✅           | Información del origen    |

#### `source`

```json
"source": {
  "generator": "jsonResultados",
  "inputs": [".\\PDF\\*.pdf"],
  "inputs_resolved": ["2026ddcc.pdf", "..."],
  "skipped": []
}
```

| Campo             | Tipo           | Descripción                    |
| ----------------- | -------------- | ------------------------------ |
| `generator`       | string         | Nombre del proceso generador   |
| `inputs`          | array\[string] | Rutas indicadas por el usuario |
| `inputs_resolved` | array\[string] | PDFs realmente procesados      |
| `skipped`         | array\[string] | PDFs ignorados                 |

***

## 3. `dimensions`

### Propósito

Define los **catálogos globales** de entidades reutilizables.

```json
"dimensions": {
  "seasons": [ ... ],
  "competitions": [ ... ],
  "clubs": [ ... ],
  "athletes": [ ... ],
  "events": [ ... ]
}
```

***

### 3.1 `seasons`

```json
{
  "id": "s_2025_2026",
  "label": "Temporada 2025-2026"
}
```

| Campo   | Tipo   | Obligatorio | Descripción         |
| ------- | ------ | ----------- | ------------------- |
| `id`    | string | ✅           | Identificador único |
| `label` | string | ✅           | Nombre descriptivo  |

***

### 3.2 `competitions`

```json
{
  "id": "c_2025_10_25_madrid_1_jornada_xxvi_liga_espanola_clubes_master",
  "season_id": "s_2025_2026",
  "name": "1ª Jornada – Fase Territorial – XXVI Liga Española Clubes Máster",
  "name_clean": "1ª Jornada - XXVI Liga Española Clubes Máster",
  "date": "2025-10-25",
  "date_start": "2025-10-25",
  "date_end": "2025-10-26",
  "location": "Valdemoro",
  "region": "Madrid",
  "pool_type": "M 25",
  "source_file": "202601ddcc.pdf"
}
```

| Campo         | Tipo          | Obligatorio | Descripción               |
| ------------- | ------------- | ----------- | ------------------------- |
| `id`          | string        | ✅           | ID único                  |
| `season_id`   | string        | ✅           | Referencia a `seasons.id` |
| `name`        | string        | ✅           | Nombre original           |
| `name_clean`  | string        | ✅           | Nombre normalizado        |
| `date`        | string        | ✅           | Fecha principal           |
| `date_start`  | string        | ✅           | Inicio                    |
| `date_end`    | string / null | ❌           | Fin                       |
| `location`    | string        | ✅           | Sede                      |
| `region`      | string        | ❌           | Región                    |
| `pool_type`   | string        | ❌           | Tipo de piscina           |
| `source_file` | string        | ✅           | PDF origen                |

***

### 3.3 `clubs`

```json
{
  "id": "club_c_d_e_pacifico_salvamento",
  "name": "C.D.E Pacífico Salvamento",
  "slug": "c_d_e_pacifico_salvamento"
}
```

| Campo  | Tipo   | Obligatorio | Descripción         |
| ------ | ------ | ----------- | ------------------- |
| `id`   | string | ✅           | Identificador único |
| `name` | string | ✅           | Nombre oficial      |
| `slug` | string | ✅           | Versión normalizada |

***

### 3.4 `athletes`

```json
{
  "id": "a_maria_fernandez_rodriguez_2001",
  "name": "María Fernández Rodríguez",
  "birth_year": 2001
}
```

| Campo        | Tipo          | Obligatorio | Descripción         |
| ------------ | ------------- | ----------- | ------------------- |
| `id`         | string        | ✅           | Identificador único |
| `name`       | string        | ✅           | Nombre completo     |
| `birth_year` | number / null | ❌           | Año de nacimiento   |

> En relevos puede ser `null`. Este caso se da si en el PDF no hay datos de relevistas. En este caso el deportista es el nombre del club y no tiene año. También puede darse si el deportista sólo participa en pruebas de relevos. En estos casos el PDF no tiene fecha de nacimiento del deportista.

***

### 3.5 `events`

```json
{
  "id": "e_50_m_natacion_con_obstaculos_absoluto_f",
  "base": "50 m Natación con Obstáculos",
  "discipline": "Natación con Obstáculos",
  "category": "Absoluto",
  "sex": "F",
  "relay": false,
  "distance_m": "50"
}
```

| Campo        | Tipo                 | Obligatorio | Descripción |
| ------------ | -------------------- | ----------- | ----------- |
| `id`         | string               | ✅           | ID único    |
| `base`       | string               | ✅           | Nombre base |
| `discipline` | string               | ✅           | Disciplina  |
| `category`   | string               | ✅           | Categoría   |
| `sex`        | string (`M`,`F`,`X`) | ✅           | Sexo        |
| `relay`      | boolean              | ✅           | Es relevo   |
| `distance_m` | string / null        | ❌           | Distancia   |

category es una representación textual **siempre en femenino**, ya que concuerda con el sustantivo _categoría_. No depende del sexo de la prueba.

***

## 4. `results`

### Propósito

Vista **plana y analítica** de todos los resultados.

```json
{
  "id": "r_c_2025_10_25_madrid_toma_de_tiempos_distancias_cortas_mayores_e_50_m_natacion_con_obstaculos_absoluto_f_a_apolinar_pancho_rodriguez_1998_final",
  "date": "2025-10-25",
  "season_id": "s_2025_2026",
  "competition_id": "c_2025_10_25_madrid_toma_de_tiempos_distancias_cortas_mayores",
  "event_id": "e_50_m_natacion_con_obstaculos_absoluto_f",
  "athlete_id": "a_apolinar_pancho_rodriguez_1998",
  "club_id": "club_c_d_e_pacifico_salvamento",
  "time": { ... },
  "status": "OK",
  "position": 7,
  "points": 7,
  "series_type": "Final",
  "labels": { ... },
  "heat": null
}
```

### Campos principales

| Campo            | Tipo          | Obligatorio | Descripción   |
| ---------------- | ------------- | ----------- | ------------- |
| `id`             | string        | ✅           | ID único      |
| `date`           | string        | ✅           | Fecha         |
| `season_id`      | string        | ✅           | Temporada     |
| `competition_id` | string        | ✅           | Competición   |
| `event_id`       | string        | ✅           | Prueba        |
| `athlete_id`     | string        | ✅           | Deportista    |
| `club_id`        | string        | ✅           | Club          |
| `time`           | object / null | ❌           | Tiempo        |
| `status`         | string        | ✅           | Estado        |
| `position`       | number        | ✅           | Posición      |
| `points`         | number        | ✅           | Puntos        |
| `series_type`    | string        | ✅           | Tipo de serie |
| `labels`         | object        | ❌           | Etiquetas     |
| `heat`           | number / null | ❌           | Serie         |

#### `time`

```json
"time": {
  "display": "00:31.930",
  "seconds": 31.93,
  "raw": "00:31:93"
}
```

| Campo            | Tipo          | Obligatorio | Descripción   |
| ---------------- | ------------- | ----------- | ------------- |
| `display`        | string        | ✅         | Tiempo para mostrar.<br>Se expresa en `mm:ss.ms` |
| `seconds`        | string        | ✅         | Conversión del tiempo a segundos para gráficas.<br>Se expresa en `ss.cs` |
| `raw`            | string        | ✅         | Tiempo en el fichero de entrada.<br>Se espresa en `hh:mm:ss`. |

#### `labels`

```json
"labels": {
    "x": "2025-10-25\nToma De Tiempos Distancias Cortas Mayores"
}
```

***

### 4.1 Tratamiento de pruebas de relevos

Las pruebas de **relevos** se representan en el contrato JSON siguiendo un modelo **intencionalmente desnormalizado**, diseñado para facilitar el análisis individual sin perder la semántica de equipo.

***

#### 4.1.1 Identificación de una prueba de relevo

Una prueba se considera **relevo** cuando en la dimensión `events`:

```json
"relay": true
```

Ejemplo:

```json
{
  "id": "e_4x25_m_relevo_natacion_con_obstaculos_absoluto_f",
  "base": "4x25 m Relevo Natación con Obstáculos",
  "discipline": "Relevo Natación con Obstáculos",
  "category": "Absoluta",
  "sex": "F",
  "relay": true,
  "distance_m": "4x25"
}
```

***

#### 4.1.2 Representación en `results`

En una prueba de relevos:

*   **cada miembro del equipo genera un resultado independiente en `results`**
*   todos los resultados del mismo relevo **comparten exactamente los mismos valores de equipo**

Esto implica que:

| Campo            | Comportamiento en relevos |
| ---------------- | ------------------------- |
| `event_id`       | Común a todo el relevo    |
| `competition_id` | Común                     |
| `club_id`        | Común                     |
| `time`           | Común                     |
| `status`         | Común                     |
| `position`       | Común                     |
| `points`         | Común                     |
| `series_type`    | Común                     |

La única diferencia entre las filas es:

*   `athlete_id`

***

#### 4.1.3 Campo `athlete_id` en relevos

En pruebas de relevos:

*   `athlete_id` **no representa a una persona individual**
*   representa al **miembro del relevo en ese resultado**

Cuando los nombres individuales **no están disponibles en el PDF**:

*   se utiliza un `athlete_id` sintético,
*   normalmente asociado al club,
*   con `birth_year = null`.

Ejemplo en `dimensions.athletes`:

```json
{
  "id": "a_c_d_e_pacifico_salvamento_na",
  "name": "C.D.E. Pacífico Salvamento",
  "birth_year": null
}
```

Esto **no representa un atleta real**, sino un **placeholder técnico**.

***

#### 4.1.4 Campo `time` en relevos

El campo `time` en relevos:

*   corresponde al **tiempo total del equipo**
*   es idéntico para todos los miembros del relevo

Ejemplo:

```json
"time": {
  "display": "00:59.670",
  "seconds": 59.67,
  "raw": "00:59:67"
}
```

No existe descomposición por parcial o posta en el contrato actual.

***

#### 4.1.5 Campo `status` en relevos

El estado (`status`) se aplica **al equipo completo**:

| Estado | Significado              |
| ------ | ------------------------ |
| `OK`   | Relevo válido            |
| `DSQ`  | Equipo descalificado     |
| `DNF`  | El equipo no finaliza    |
| `DNS`  | El equipo no se presenta |

Si un relevo es `DSQ`:

*   **todos los resultados asociados lo son**
*   el campo `time` puede ser `null`

***

#### 4.1.6 Campo `position` y `points` en relevos

*   `position` representa la **clasificación del equipo**
*   `points` representa los **puntos del equipo**

Estos valores se **replican en cada fila de resultado** del relevo.

Esto permite:

*   ranking individual por deportista,
*   estadísticas sin lógica especial para relevos,
*   consultas simples sin joins adicionales.

***

#### 4.1.7 Justificación del modelo

Este modelo se ha elegido deliberadamente porque:

*   evita estructuras especiales para relevos,
*   permite tratar todos los resultados de forma homogénea,
*   simplifica análisis estadístico y visualización,
*   evita perder información al desnormalizar.

El coste asumido es:

*   duplicación controlada de datos,
*   compensada por simplicidad y robustez.

***

#### 4.1.8 Recomendaciones para consumidores del JSON

*   Para análisis individuales: usar `results` directamente.
*   Para análisis por equipo: agrupar por  
    `competition_id + event_id + club_id`.
*   Para distinguir relevos: usar `events.relay == true`.
*   **No asumir** que `athlete_id` siempre representa una persona real.

***

#### 4.1.9 Compatibilidad futura

El contrato permite en el futuro:

*   añadir miembros reales del relevo,
*   añadir orden de posta,
*   añadir parciales,
*   sin romper compatibilidad hacia atrás.

***

## 5. `tree`

### Propósito

Vista **jerárquica** para interfaces gráficas.

Estructura general:

```text
season
 └─ competition
     └─ event
         └─ athlete/result
```

### Uso recomendado

*   navegación,
*   presentación en web,
*   tablas jerárquicas.

> **No es la fuente recomendada para análisis**.

***

## 6. Reglas del contrato

*   los IDs son **estables**
*   no se eliminan campos en versiones menores
*   los campos nuevos son opcionales
*   `null` indica dato no disponible, no error
*   los resultados nunca se inventan

***

## 7. Compatibilidad y versionado

*   cambios incompatibles → **major**
*   campos nuevos → **minor**
*   correcciones internas → **patch**

Consultar siempre:

```json
meta.version
```
