# USER\_GUIDE.md

## Guía de usuario

**Proyecto**: Pacifico – Conversión de resultados deportivos a JSON  
**Audiencia**: Usuarios finales, analistas, consumidores de datos  
**Nivel técnico requerido**: Básico  
**Versión del documento**: 1.0.0

***

## 1. ¿Para qué sirve este proyecto?

Este proyecto permite convertir **actas oficiales de competiciones deportivas en PDF** en un **fichero JSON estructurado**, homogéneo y reutilizable.

Está pensado para personas que quieren:

*   consultar resultados de competiciones,
*   analizar datos por temporada, prueba, club o deportista,
*   alimentar una web, dashboard o aplicación,
*   mantener históricos de resultados sin duplicados.

👉 **No necesitas conocer cómo funciona internamente el programa** para usarlo.

***

## 2. Qué hace el programa (visión general)

El programa:

1.  Lee uno o varios archivos **PDF** con resultados
2.  Extrae la información relevante de las competiciones
3.  Normaliza nombres, pruebas y tiempos
4.  Genera **un único fichero JSON** con todos los datos

Si ejecutas el programa varias veces con los mismos PDFs:

*   **no se duplican los datos**
*   el resultado es consistente

***

## 3. Directorio base de entrada (PDF)

Todos los PDFs de entrada se buscan **siempre** bajo el directorio:

- `./PDF`

Ejemplos válidos de ejecución:
```bash
python pdf2json.py 2026mad.pdf
python pdf2json.py 2025-2026/2026mad.pdf
python pdf2json.py 2025-2026/*.pdf
```

***

## 4. Archivos de entrada

### 4.1 Qué archivos se pueden usar como entrada

*   Archivos **PDF**
*   Deben contener **resultados oficiales de competiciones**
*   Un PDF puede incluir:
    *   varias pruebas,
    *   pruebas individuales y de relevos,
    *   uno o varios días de competición.

Ejemplo:

```text
data/PDFs/
├── 2026_01_mayores.pdf
├── 2026_02_menores.pdf
└── 2026_master.pdf
```

***

### 4.2 Qué contenido se ignora automáticamente

El programa ignora sin que tengas que hacer nada:

*   clasificaciones generales,
*   resúmenes sin detalle por prueba,
*   páginas informativas sin resultados.

***

## 5. Cómo ejecutar el programa

> ⚠️ Antes de continuar, asegúrate de haber seguido **INSTALLATION\_GUIDE.md**

***

### 5.1 Ejecución básica (un PDF)

Desde la carpeta del proyecto:

```bash
python pdf2json.py data/PDFs/2026_01_mayores.pdf
```

Qué ocurre:

*   se procesa el PDF,
*   se genera un fichero JSON de salida.
*   * el JSON se guarda en `./JSON/updatePacifico<fecha_ejecución>.json`.

***

### 5.2 Ejecutar varios PDFs a la vez

Puedes procesar varios PDFs en una sola ejecución.

#### Windows (PowerShell)

```powershell
python pdf2json.py 2026mad.pdf o python pdf2json.py 2025-2026/*.pdf (si quieres usar patrones)
```

#### Linux / macOS

```bash
python pdf2json.py 2026mad.pdf o python pdf2json.py 2025-2026/*.pdf (si quieres usar patrones)
```

Resultado:

*   todos los PDFs se combinan en **un único JSON**
*   los datos se integran sin duplicados.

***

## 6. Argumentos del programa

El programa se ejecuta desde línea de comandos y acepta varios argumentos.

### 6.1 PDFs de entrada (obligatorio)

```text
python pdf2json.py <pdf1> <pdf2> ...
```

*   Puedes pasar:
    *   un archivo,
    *   varios archivos,
    *   comodines (`*.pdf`).

👉 **Este argumento define qué datos se procesan.**

***

### 6.2 Filtro de club (`--club`)

(opcional) Filtra los resultados por club (argumento repetible).
Puedes filtrar la salida para quedarte solo con los resultados de uno o varios clubes. Por defecto se filtra sólo para Pacifico.

Ejemplo 1 (si no se especifica el argumento se filtra para Pacifico):
```bash
python pdf2json.py 2026mad.pdf o python pdf2json.py 2025-2026/202501mayores.pdf o python pdf2json.py 2025-2026/*.pdf
```

Ejemplo 2 (un club):
```bash
python pdf2json.py 2026mad.pdf --club Pacifico
```

El resultado de los ejemplos 1 y 2 es el mismo.

Ejemplo 3 (varios filtros; se aceptan múltiples ocurrencias):
```bash
python pdf2json.py 2026mad.pdf --club Pacifico --club Canoe
```

***

### 6.3 Trace (`--trace`) (opcional)

(opcional) Genera un fichero de trazabilidad del parsing.
Si activas `--trace`, se genera un fichero de trazabilidad en:

- `./JSON/trace/<salida>.jsonl`

donde `<salida>` es el nombre del JSON de salida sin `.json`.

Si no se especifica `--trace`, no se genera ningún fichero.

***

### 6.4 Dump del texto extraído (`--dump`)

(opcional) Genera un dump del texto extraído del PDF (extract_text).
Si necesitas depurar qué texto leyó el extractor del PDF, puedes generar un dump:

```bash
python pdf2json.py 2026mad.pdf --club Pacifico --dump
```
Se generará un fichero en:
*   ./JSON/dump/<nombre_json_salida>.txt

***

### 6.5 Modo estricto (`--strict`)

(opcional) Si un PDF provoca un error de parsing, el programa se detiene y no genera salida parcial.

```bash
python pdf2json.py 2026mad.pdf --strict
```

Qué hace:

*   si se detecta un error de parsing, el programa se detiene,
*   no se genera salida parcial.

Cuándo usarlo:

*   para comprobar la calidad de un PDF nuevo,
*   para depurar problemas.

Modo normal (sin `--strict`):

*   es tolerante a errores,
*   siempre intenta generar salida.

***

### 6.6 Modo depuración (`--debug`)

(opcional) Muestra información detallada por consola durante la ejecución (útil para depuración).

***

## 7. Archivo de salida

### 7.1 Qué se genera como salida

El programa genera un **fichero JSON** en:

  `./JSON/updatePacifico<fecha_ejecución>.json`

El nombre incluye la fecha y hora de ejecución para evitar sobrescrituras.
No existe ningún argumento para cambiar el nombre o la carpeta de salida.

El fichero JSON tiene esta esta estructura general:

```json
{
  "meta": { ... },
  "dimensions": { ... },
  "results": [ ... ],
  "tree": [ ... ]
}
```

***

### 7.2 `meta`

Contiene información descriptiva:

*   versión del formato,
*   fecha de generación,
*   archivos de entrada utilizados.

Sirve para:

*   trazabilidad,
*   auditorías,
*   control de versiones.

***

### 7.3 `dimensions`

Incluye los elementos “globales”:

*   temporadas,
*   competiciones,
*   pruebas,
*   clubes,
*   deportistas.

Características importantes:

*   no hay duplicados,
*   los identificadores son estables,
*   se reutilizan entre competiciones y temporadas.

***

### 7.4 `results` (la parte más importante)

Cada elemento de `results` representa:

> **Un deportista en una prueba concreta, en una competición concreta**

Incluye, entre otros:

*   deportista,
*   club,
*   prueba,
*   tiempo,
*   posición,
*   estado del resultado.

👉 **Esta es la sección recomendada para análisis, gráficos y estadísticas.**

***

### 7.5 `tree`

`tree` es una vista jerárquica pensada para interfaces gráficas:

*   temporada → competición → prueba → resultados.

Útil para:

*   navegación,
*   visualización en webs.

⚠️ No se recomienda usarla para cálculos o cruces complejos.

***

### 7.6 Ubicación y nombre del fichero generado (importante)
El programa genera **siempre** el JSON en esta ruta:

- `./JSON/updatePacifico<fecha_ejecución>.json`

Donde `<fecha_ejecución>` corresponde al momento de ejecución (por ejemplo: `20260324_142530`).

⚠️ **No existe un argumento para cambiar el nombre o la carpeta de salida.**

***

## 8. Interpretación de resultados

### 8.1 Pruebas individuales

*   Cada fila del PDF genera un resultado.
*   El deportista tiene año de nacimiento.
*   Puede haber resultados de:
    *   series preliminares,
    *   finales.

***

### 8.2 Pruebas de relevos

En relevos:

*   el resultado es del equipo,
*   el sistema genera **un resultado por cada miembro** del relevo.

Todos los miembros comparten:

*   tiempo,
*   posición,
*   estado.

Esto permite:

*   estadísticas individuales,
*   análisis por deportista,
*   sin perder información de equipo.

***

### 8.3 Estados de un resultado

Valores habituales:

| Estado | Significado      |
| ------ | ---------------- |
| `OK`   | Resultado válido |
| `DSQ`  | Descalificado    |
| `DNF`  | No finaliza      |
| `DNS`  | No se presenta   |
| `BAJA` | Baja             |

En resultados no válidos:

*   el tiempo puede ser `null`,
*   el resultado sigue existiendo.

***

## 9. Identificadores (IDs): lo que debes saber

Como usuario, puedes confiar en que:

*   los IDs son **estables en el tiempo**,
*   no cambian al reprocesar datos,
*   no se duplican,
*   pueden usarse como claves en otras aplicaciones.

Ejemplos:

*   un club siempre tiene el mismo ID,
*   un deportista es el mismo aunque aparezca en muchas competiciones.

***

## 10. Actualizar datos con nuevas competiciones

Uso típico:

1.  Procesas una primera tanda de PDFs
2.  Guardas el JSON generado
3.  Más adelante procesas nuevos PDFs
4.  Se combinan con los datos existentes

Garantías:

*   no se pierden datos antiguos,
*   no se duplican resultados,
*   el histórico se mantiene coherente.

***

## 11. Errores y advertencias comunes

*   PDFs mal escaneados pueden producir resultados incompletos
*   Si un dato no existe en el PDF, **no se inventa**
*   El programa prioriza siempre la fidelidad al acta original

***

## 12. Documentación relacionada

| Documento                | Para qué sirve                    |
| ------------------------ | --------------------------------- |
| `INSTALLATION_GUIDE.md`  | Instalación y ejecución           |
| `USER_GUIDE.md`          | Uso del programa (este documento) |
| `JSON_CONTRACT.md`       | Referencia técnica del JSON       |
| `TECHNICAL_REFERENCE.md` | Funcionamiento interno            |

***

## 13. Resumen rápido

✅ Ejecutas el programa con PDFs  
✅ Obtienes un JSON estructurado  
✅ Usas `results` para análisis  
✅ Usas `tree` para navegación  
✅ Puedes actualizar datos sin duplicados
