# Pacífico
### Conversión de resultados deportivos a JSON estructurado

![python](https://img.shields.io/badge/python-3.10%2B-blue)
![license](https://img.shields.io/badge/license-AGPL--3.0--or--later-green)
![status](https://img.shields.io/badge/status-stable-brightgreen)

**Pacifico** es una herramienta open‑source para convertir **resultados deportivos oficiales (PDF y Excel)** en un **JSON estructurado, normalizado y reutilizable**, orientado a análisis, visualización y consumo por aplicaciones externas.

El proyecto está diseñado para ser **determinista, trazable y mantenible**, incluso con fuentes heterogéneas o con problemas de formato (OCR en PDFs, Excel inconsistentes, etc.).

***

## Características principales

- Procesa **PDFs oficiales de resultados**
- Procesa **ficheros Excel** (`.xls`, `.xlsx`, `.xlsm`)
- Modelo **relacional canónico** (dimensions + results)
- **Idempotente**: reprocesar datos no genera duplicados
- **IDs estables** entre ejecuciones y temporadas
- Soporte completo de **pruebas individuales y relevos**
- Tolerante a errores de formato y OCR
- Salida en **JSON versionado y documentado**

***

## Casos de uso

*   Análisis histórico de resultados deportivos
*   Dashboards y visualización (Plotly, D3, etc.)
*   Integración con aplicaciones web
*   Normalización de datos oficiales dispersos
*   Archivado y auditoría de competiciones

***

## Estructura del proyecto

```text
.
├── jsonResultados.py        # CLI principal (PDF + XLS)
├── results2json          # Núcleo del parser y normalización
├── tools/                   # Herramientas auxiliares
│   └── txt2json.py          # Fixtures TXT (solo tests)
├── requirements.txt
├── docs/
│   ├── INSTALLATION_GUIDE.md
│   ├── USER_GUIDE.md
│   ├── JSON_CONTRACT.md
│   └── TECHNICAL_REFERENCE.md
├── LICENSE
└── README.md
```

***

## Uso rápido

### Uso normal (PDF / Excel orientado al club Pacífico)

```bash
python jsonResultados.py *.pdf
python jsonResultados.py resultados.xlsx
python jsonResultados.py *.pdf datos.xls
```

Por convención:

* Los PDFs se buscan bajo ./PDF (no es necesario indicar la ruta)
* Los Excel se pasan por ruta directa o patrón
* Si no se especifica --club, se filtra automáticamente por Pacífico
* El resultado se guarda siempre en:

```text
./JSON/updatePacifico<fecha_ejecución>.json
```

Resultado:

*   un fichero JSON con:
    *   resultados para el club Pacífico
    *   entidades normalizadas (temporadas, competiciones, clubes, atletas),
    *   resultados individuales y de relevos,
    *   estructura jerárquica para navegación.

### Con opciones de depuración

```bash
python pdf2json.py 2025-2026/*.pdf --trace --dump --debug
```

Genera:

* Trace en ./JSON/trace/<salida>.jsonl
* Dump de texto en ./JSON/dump/<salida>.txt

***

### Uso con ficheros TXT (solo pruebas)

Los ficheros .txt no son una fuente de entrada normal.
Se utilizan únicamente como fixtures de test, simulando la salida de PDFs.

```bash
python -m tools.txt2json tests/fixtures/text/ejemplo.txt --debug
```

Para más detalles, consulta README_TOOLS.md.

***

## Instalación

Consulta la guía completa:

**docs/INSTALLATION\_GUIDE.md**  

Incluye:

*   requisitos,
*   entorno virtual,
*   instalación de dependencias,
*   ejecución en Windows / Linux / macOS.

***

## Documentación

La documentación es parte esencial del proyecto y se mantiene **versionada junto al código**.

| Documento                   | Descripción                       |
| --------------------------- | --------------------------------- |
| `INSTALLATION_GUIDE.md`  | Instalación y ejecución           |
| `USER_GUIDE.md`          | Uso funcional del JSON generado.<br>Guía para usuarios finales.|
| `JSON_CONTRACT.md`       | Especificación técnica del JSON   |
| `TECHNICAL_REFERENCE.md` | Arquitectura y Knowledge Transfer |

> Nota: Los diagramas están escritos en **Mermaid** y se renderizan automáticamente en GitHub/GitLab.  
> En VS Code es necesario instalar una extensión de Mermaid para el preview.

***

## Principios de diseño

*   **No invención de datos**  
    Si un dato no está en la fuente, no se genera.

*   **Estabilidad de identificadores**  
    Los IDs no cambian entre ejecuciones.

*   **Modelo canónico**  
    Separación clara entre dimensiones y resultados.

*   **Relevos desnormalizados**  
    Un resultado por miembro cuando existe para facilitar análisis.

*   **Pipeline tolerante a errores**  
    El sistema prioriza no perder información válida.

***

## Tecnologías

*   Python 3.10+
*   Parsing de PDF
*   JSON estructurado
*   Markdown + Mermaid para documentación

***

## Contribuciones

Las contribuciones son bienvenidas.

Antes de abrir un PR:

1.  Revisa `TECHNICAL_REFERENCE.md`
2.  Respeta el contrato definido en `JSON_CONTRACT.md`
3.  Mantén la idempotencia y estabilidad de IDs
4.  Documenta cualquier cambio visible

Para cambios grandes o de diseño, abre primero un **issue**.

***

## Estado del proyecto

*   Parser funcional
*   Contrato JSON estable
*   Documentación completa
*   Listo para uso y mantenimiento

***

## Licencia

Este proyecto se distribuye bajo licencia **AGPL‑3.0‑or‑later**.

Consulta el fichero LICENSE para más información.

***

## Contacto / Soporte

Para dudas, problemas o propuestas:

*   abre un **issue** en el repositorio,
*   o documenta el caso con un PDF de ejemplo (si es posible).

***
