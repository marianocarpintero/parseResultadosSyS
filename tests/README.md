# Sefltest.py

## Ejecución

``` bash
python -m tests.selftest
```

## Salida típica

``` txt
PS C:\GitProjects\parseResultadosSyS> python -m tests.selftest  
[OK ] header_definitivos_guion.txt
      pages=2  events=1  results=1  athletes=1  clubs=1
[OK ] master_multiple.txt
      pages=1  events=2  results=2  athletes=2  clubs=1
[OK ] relay_cross_page.txt
      pages=2  events=1  results=4  athletes=4  clubs=1

Resumen: OK=3 FAIL=0
==================================================
SELFTEST SUMMARY
fixtures: 3   OK: 3   FAIL: 0
==================================================
```








Perfecto. Con el **`selftest.py` ya funcionando** y `iter_text_pages()` integrado, ahora toca lo más valioso: **diseñar bien el dataset de fixtures TXT** para cubrir **todos los casos reales y bordes** que existen hoy en `pdf2json` / `pdf2tree`.

Lo que te voy a dar ahora es:

1.  **Un repaso sistemático del flujo real de tu código** (qué decisiones toma).
2.  **Una lista exhaustiva de casos de uso / edge cases** que aparecen en ese flujo.
3.  **Propuesta concreta de TXT adicionales**, con nombre, objetivo y qué asserts deberían validar.

No es código todavía: es **arquitectura de test data**, para que lo hagas una sola vez y te cubra el futuro.

***

## 1. Flujo real del `pdf2json` (resumen técnico)

Simplificando, tu pipeline hace esto:

1.  **Entrada por página**
    *   Página relevante / ignorada (clasificación general, etc.)
2.  **Parseo de cabecera**
    *   Nombre competición
    *   Lugar
    *   Fecha(s)
    *   Pool
3.  **Detección de evento**
    *   EVENT\_TITLE
    *   CATEGORY\_LINE
    *   SEX
    *   Distancia / disciplina
4.  **Parseo de tabla**
    *   TABLE\_HEADER
    *   Filas individuales
    *   Filas de relevo
5.  **Estados delicados**
    *   Cambio de evento
    *   Cambio de página
    *   Ruido (direcciones, pies, notas)
6.  **Flush defensivo**
    *   Final de página
    *   Nuevo evento
    *   finalize()
7.  **Post-proceso**
    *   Remapeo atleta \_na → con año
    *   IDs
    *   Categoría femenina
    *   Máster display
    *   Filtro de club

👉 Tus fixtures TXT deben **forzar cada uno de esos puntos**.

***

## 2. Casos de uso ya cubiertos (bien)

Por lo que has montado hasta ahora, ya tienes:

✅ `header_definitivos_guion.txt`

*   Limpieza de cabeceras
*   Guiones finales
*   “DEFINITIVOS”

✅ `master_multiple.txt`

*   Categorías máster múltiples
*   No colar rangos combinados en `event_id`
*   Display `Máster` correcto

✅ `relay_cross_page.txt`

*   Relevo cruzando página
*   Ruido con coma/números
*   No cerrar relevo prematuramente

Esto es una **base excelente**.

***

## 3. Casos de uso IMPORTANTES que AÚN NO tienes

Ahora, revisando el código y bugs históricos, te recomiendo **añadir estos TXT**.

***

## 4. Nuevos TXT recomendados (priorizados)

### 🥇 1. `individual_missing_position.txt`

**Caso real**: PDFs donde la posición **no se lee**, pero el resto está.

**Qué simula**

*   Fila individual sin posición numérica inicial
*   Todo lo demás correcto

**Por qué es crítico**

*   Ya tuviste bugs donde:
    *   se infería posición 1
    *   o se perdía el resultado
*   La posición puede ser `None`, pero **el result debe existir**

**Qué validar**

*   `results == 1`
*   `position is None`
*   `status == OK`
*   `result_id` correcto (no `_na` raro)

***

### 🥇 2. `individual_dsq_dns_dnf.txt`

**Estados no OK** en individuales.

**Qué simula**
Tres filas:

```text
DSQ
DNS
DNF
```

**Por qué es crítico**

*   El parser cambia:
    *   tiempo → `null`
    *   score/points
*   El result **NO debe desaparecer**
*   IDs deben ser estables

**Qué validar**

*   3 resultados
*   `time.raw == None`
*   `status` correcto en cada uno

***

### 🥇 3. `relay_flush_on_new_event.txt`

**Flush defensivo al cambiar de evento**.

**Qué simula**

*   Relevo incompleto
*   Aparece un nuevo EVENT\_TITLE antes del 4º miembro

**Por qué es crítico**

*   Código complejo (`expected_size`, `flush_context`)
*   Ya lo tocaste varias veces
*   Si falla, se pierden miembros o se cuelan nombres

**Qué validar**

*   Relevo se cierra
*   Nº de resultados ≤ miembros leídos
*   El siguiente evento empieza limpio

***

### 🥈 4. `lanzamiento_cuerda_2_miembros.txt`

**Relevo especial** (no 4x).

**Qué simula**

*   Lanzamiento de cuerda
*   Solo 2 miembros
*   Sin distancia

**Por qué es crítico**

*   Es un outlier semántico
*   El parser no puede asumir “4”

**Qué validar**

*   `expected_results == 2`
*   `distance_m is None`
*   `discipline == "Lanzamiento de Cuerda"`

***

### 🥈 5. `category_line_split_over_pages.txt`

**CATEGORY\_LINE partida entre páginas**.

**Qué simula**

```text
PAGE 1:
Máster 30-34 (Mas

PAGE 2:
culina)
```

**Por qué es crítico**

*   PDFs mal cortados
*   OCR raro
*   CATEGORY\_LINE no atómica

**Qué validar**

*   Categoría correctamente reconstruida
*   No se clasifica como NOISE

***

### 🥈 6. `misleading_person_like_noise.txt`

**Ruido que parece nombre**.

Ejemplo:

```text
JUAN CARLOS S.L.
```

O:

```text
C/ GENERAL MOSCARDÓ
```

**Por qué**

*   `looks_like_person_name()` es heurístico
*   Si falla → fake athletes

**Qué validar**

*   No se crea atleta
*   No se añade result
*   Trace marque `REJECT_RELAY_MEMBER` (si aplicable)

***

### 🥉 7. `multiple_tables_same_event.txt`

**Dos tablas consecutivas para el mismo evento**.

**Qué simula**

*   Series + Final
*   Mismo EVENT\_TITLE
*   TABLE\_HEADER reaparece

**Por qué**

*   El parser no debe crear **dos eventos**
*   Debe diferenciar por `series_type`

**Qué validar**

*   `events == 1`
*   `results` con series distintas

***

### 🥉 8. `classification_page_ignored.txt`

**Página entera ignorada**.

**Qué simula**

```text
CLASIFICACIÓN GENERAL
```

**Qué validar**

*   No se crean:
    *   atletas
    *   clubes
    *   resultados
*   La página se ignora completamente

***

## 5. Propuesta de nombres finales (limpios)

Te propongo este set final para `tests/fixtures/text/`:

    header_definitivos_guion.txt
    master_multiple.txt
    relay_cross_page.txt

    individual_missing_position.txt
    individual_dsq_dns_dnf.txt
    relay_flush_on_new_event.txt
    lanzamiento_cuerda_2_miembros.txt
    category_line_split_over_pages.txt
    misleading_person_like_noise.txt
    multiple_tables_same_event.txt
    classification_page_ignored.txt

No necesitas todos el mismo día, pero **estos 10 cubren \~95 % de los bugs reales** que has tenido y los que puedes volver a tener.

***

## 6. Cómo integrarlos en `selftest.py` (modelo mental)

Para cada nuevo TXT:

1.  Añades el fichero
2.  Añades su entrada en `FIXTURE_SPECS`:
    ```python
    "individual_missing_position.txt": {
        "expect_results": 1,
        "expect_events": 1,
        "expect_all_results": {
            "position": None
        }
    }
    ```
3.  Si mañana refactorizas parser/tokenizer y algo se rompe → lo sabrás **en segundos**

***

## 7. Siguiente paso recomendado

Si quieres, en el próximo mensaje puedo:

*   **crear 2–3 de estos TXT completos** (copypasteables)
*   o ayudarte a **priorizar solo los 3 más rentables** para empezar
*   o diseñar un **“fixture template”** para que los escribas tú rápido

