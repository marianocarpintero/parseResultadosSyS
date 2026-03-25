Perfecto. Antes de tocar **`tokenizer.py`**, te propongo **definir explícitamente qué tokens vamos a reconocer, cuáles vamos a normalizar y cuáles vamos a introducir nuevos**, junto con **las condiciones exactas** bajo las que se activan. Así luego el código será casi mecánico.

Voy a asumir el contexto de **resultados de salvamento/socorrismo** que ya manejas en *Pacifico*.

***

## 1. Objetivo del tokenizer (recordatorio rápido)

El tokenizer debe:

*   Convertir texto OCR/PDF “sucio” en **tokens semánticos estables**
*   Reducir ambigüedades **antes** del parser (eventos, atletas, categorías)
*   Ser **determinista y conservador** (mejor no tokenizar que tokenizar mal)

***

## 2. Tokens existentes que conviene **tocar / reforzar**

### 2.1. `DISTANCE`

**Ejemplos**

*   `50 m`, `100m`, `200 m.`, `4x50 m`

**Condiciones**

*   Número entero (`\d+`)
*   Opcional `x` para relevos (`4x50`)
*   `m` literal (con o sin espacio)
*   Normalizar a:
    ```text
    100 m
    4x50 m
    ```

✅ Acción:

*   Asegurar que **`4x50` no se rompa en `4` + `x50`**
*   Unificar espacio: siempre `␠m`

***

### 2.2. `STYLE` / `DISCIPLINA`

**Ejemplos**

*   `libre`
*   `socorrista`
*   `arrastre de maniquí`
*   `remolque de maniquí con aletas`
*   `obstáculos`

**Condiciones**

*   Coincidencia contra **diccionario cerrado**
*   Puede ser **multi‐palabra**
*   Case-insensitive

✅ Acción:

*   Token **único**, no palabra a palabra
*   Prioridad **sobre tokens genéricos**

***

### 2.3. `CATEGORY`

**Ejemplos**

*   `Infantil`
*   `Cadete`
*   `Juvenil`
*   `Junior`
*   `Absoluto`
*   `Master 30-34`

**Condiciones**

*   Match exacto o abreviado:
    *   `Inf` → `Infantil`
    *   `Cad` → `Cadete`
*   Puede ir seguida de rango de edad

✅ Acción:

*   Normalizar siempre a masculino singular
*   Separar:
    *   `CATEGORY`
    *   `AGE_RANGE` (ver abajo)

***

## 3. Tokens nuevos que **debemos añadir**

### 3.4. `AGE_RANGE`

**Ejemplos**

*   `30-34`
*   `70-74`

**Condiciones**

*   Regex: `\d{2}\s*-\s*\d{2}`
*   **Solo válido** si:
    *   Está cerca de `Master`
    *   O dentro de contexto de categoría

✅ Acción:

*   Token independiente
*   Nunca inferir categoría solo por rango

***

### 3.5. `GENDER`

**Ejemplos**

*   `Masculino`, `Femenino`
*   `M`, `F`
*   `Mixto`

**Condiciones**

*   Aparece en cabecera de prueba
*   O al final de nombre de evento

✅ Acción:

*   Normalizar a:
    ```json
    "gender": "M" | "F" | "X"
    ```

***

### 3.6. `RELAY_MARKER`

**Ejemplos**

*   `4x`
*   `relevos`
*   `relay`

**Condiciones**

*   `NxDISTANCE`
*   Palabra clave contextual

✅ Acción:

*   Token booleano:
    ```json
    "is_relay": true
    ```
*   Importante para **no exigir año de nacimiento**

***

### 3.7. `ATHLETE_NAME`

**Ejemplos**

*   `García Pérez, Juan`
*   `Juan García`

**Condiciones**

*   Letras + espacios
*   Excluir:
    *   Categorías
    *   Clubes
    *   Disciplina

✅ Acción:

*   No normalizar aquí (eso es del parser)
*   Solo **marcar span**

***

### 3.8. `CLUB`

**Ejemplos**

*   `C.D.E. Pacífico`
*   `Real Canoe`
*   `CN Alcorcón`

**Condiciones**

*   Match contra **lista conocida** (si existe)
*   O patrón típico:
    *   `C.D.`
    *   `C.N.`
    *   `A.D.`

✅ Acción:

*   Token prioritario
*   Evita confundir con atleta

***

## 4. Tokens que **debemos ignorar / filtrar**

### 4.9. `NOISE`

**Ejemplos**

*   `clasificación general`
*   `página`
*   `resultados`
*   encabezados repetidos

✅ Acción:

*   Token descartable
*   El tokenizer **puede eliminar la línea completa**

***

## 5. Orden de prioridad (clave)

El tokenizer debe aplicar tokens en este orden:

1.  `NOISE`
2.  `DISTANCE` / `RELAY_MARKER`
3.  `STYLE`
4.  `CATEGORY`
5.  `AGE_RANGE`
6.  `GENDER`
7.  `CLUB`
8.  `ATHLETE_NAME`
9.  `GENERIC_WORD`

Esto evita casos como:

*   `Master 70-74` mal troceado
*   `4x50` separado incorrectamente
*   Club interpretado como persona

***

## 6. Resultado esperado del tokenizer

Entrada:

```text
100 m Remolque de maniquí con aletas Master 70-74 Masculino
```

Salida (conceptual):

```json
[
  {"type": "DISTANCE", "value": "100 m"},
  {"type": "STYLE", "value": "remolque de maniquí con aletas"},
  {"type": "CATEGORY", "value": "Master"},
  {"type": "AGE_RANGE", "value": "70-74"},
  {"type": "GENDER", "value": "M"}
]
```

***

## 7. Siguiente paso

Si te parece bien este **contrato de tokens**, en el siguiente mensaje:

*   Entramos **directamente en `tokenizer.py`**
*   Te digo:
    *   qué funciones tocar
    *   qué regex añadir
    *   y cómo estructurarlo para que sea extensible

👉 Dime si **añadirías / quitarías algún token** antes de pasar al código.
