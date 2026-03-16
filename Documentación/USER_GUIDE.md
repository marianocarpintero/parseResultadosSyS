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

## 3. Archivos de entrada

### 3.1 Qué archivos se pueden usar como entrada

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

### 3.2 Qué contenido se ignora automáticamente

El programa ignora sin que tengas que hacer nada:

*   clasificaciones generales,
*   resúmenes sin detalle por prueba,
*   páginas informativas sin resultados.

***

## 4. Cómo ejecutar el programa

> ⚠️ Antes de continuar, asegúrate de haber seguido **INSTALLATION\_GUIDE.md**

***

### 4.1 Ejecución básica (un PDF)

Desde la carpeta del proyecto:

```bash
python pdf2json.py data/PDFs/2026_01_mayores.pdf
```

Qué ocurre:

*   se procesa el PDF,
*   se genera un fichero JSON de salida.

***

### 4.2 Ejecutar varios PDFs a la vez

Puedes procesar varios PDFs en una sola ejecución.

#### Windows (PowerShell)

```powershell
python pdf2json.py data\PDFs\*.pdf
```

#### Linux / macOS

```bash
python pdf2json.py data/PDFs/*.pdf
```

Resultado:

*   todos los PDFs se combinan en **un único JSON**
*   los datos se integran sin duplicados.

***

## 5. Argumentos del programa

El programa se ejecuta desde línea de comandos y acepta varios argumentos.

### 5.1 PDFs de entrada (obligatorio)

```text
python pdf2json.py <pdf1> <pdf2> ...
```

*   Puedes pasar:
    *   un archivo,
    *   varios archivos,
    *   comodines (`*.pdf`).

👉 **Este argumento define qué datos se procesan.**

***

### 5.2 Modo estricto (`--strict`)

```bash
python pdf2json.py data/PDFs/*.pdf --strict
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

## 6. Archivo de salida

### 6.1 Qué se genera como salida

El programa genera un **fichero JSON** con esta estructura general:

```json
{
  "meta": { ... },
  "dimensions": { ... },
  "results": [ ... ],
  "tree": [ ... ]
}
```

***

### 6.2 `meta`

Contiene información descriptiva:

*   versión del formato,
*   fecha de generación,
*   archivos de entrada utilizados.

Sirve para:

*   trazabilidad,
*   auditorías,
*   control de versiones.

***

### 6.3 `dimensions`

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

### 6.4 `results` (la parte más importante)

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

### 6.5 `tree`

`tree` es una vista jerárquica pensada para interfaces gráficas:

*   temporada → competición → prueba → resultados.

Útil para:

*   navegación,
*   visualización en webs.

⚠️ No se recomienda usarla para cálculos o cruces complejos.

***

## 7. Interpretación de resultados

### 7.1 Pruebas individuales

*   Cada fila del PDF genera un resultado.
*   El deportista tiene año de nacimiento.
*   Puede haber resultados de:
    *   series preliminares,
    *   finales.

***

### 7.2 Pruebas de relevos

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

### 7.3 Estados de un resultado

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

## 8. Identificadores (IDs): lo que debes saber

Como usuario, puedes confiar en que:

*   los IDs son **estables en el tiempo**,
*   no cambian al reprocesar datos,
*   no se duplican,
*   pueden usarse como claves en otras aplicaciones.

Ejemplos:

*   un club siempre tiene el mismo ID,
*   un deportista es el mismo aunque aparezca en muchas competiciones.

***

## 9. Actualizar datos con nuevas competiciones

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

## 10. Errores y advertencias comunes

*   PDFs mal escaneados pueden producir resultados incompletos
*   Si un dato no existe en el PDF, **no se inventa**
*   El programa prioriza siempre la fidelidad al acta original

***

## 11. Documentación relacionada

| Documento                | Para qué sirve                    |
| ------------------------ | --------------------------------- |
| `INSTALLATION_GUIDE.md`  | Instalación y ejecución           |
| `USER_GUIDE.md`          | Uso del programa (este documento) |
| `JSON_CONTRACT.md`       | Referencia técnica del JSON       |
| `TECHNICAL_REFERENCE.md` | Funcionamiento interno            |

***

## 12. Resumen rápido

✅ Ejecutas el programa con PDFs  
✅ Obtienes un JSON estructurado  
✅ Usas `results` para análisis  
✅ Usas `tree` para navegación  
✅ Puedes actualizar datos sin duplicados
