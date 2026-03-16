# Pacifico

### Conversión de resultados deportivos a JSON estructurado

<https://img.shields.io/badge/python-3.10%2B-blue>
<https://img.shields.io/badge/license-AGPL--3.0--or--later-green>
<https://img.shields.io/badge/status-stable-brightgreen>

**Pacifico** es una herramienta open‑source para convertir **actas oficiales de competiciones deportivas en PDF** en un **JSON estructurado, normalizado y reutilizable**, orientado a análisis, visualización y consumo por aplicaciones externas.

El proyecto está diseñado para ser **determinista, trazable y mantenible**, incluso con PDFs heterogéneos o con problemas de OCR.

***

## Características principales

*   Procesa uno o varios **PDFs de resultados deportivos**
*   Modelo **relacional canónico** (dimensiones + resultados)
*   **Idempotente**: reprocesar no genera duplicados
*   **IDs estables** entre ejecuciones y temporadas
*   Soporte completo de **pruebas individuales y relevos**
*   Tolerante a errores de formato y OCR
*   Salida en **JSON versionado y documentado**

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
├── pdf2json.py              # Punto de entrada (CLI)
├── pdf2tree/                # Núcleo del parser y normalización
├── data/                    # PDFs de entrada (ejemplo)
├── requirements.txt         # Dependencias Python
├── docs/                    # Documentación Markdown
│   ├── INSTALLATION_GUIDE.md
│   ├── USER_GUIDE.md
│   ├── JSON_CONTRACT.md
│   └── TECHNICAL_REFERENCE.md
├── LICENSE
└── README.md
```

***

## Uso rápido

```bash
python pdf2json.py data/PDFs/*.pdf
```

Resultado:

*   un fichero JSON con:
    *   entidades normalizadas (temporadas, competiciones, clubes, atletas),
    *   resultados individuales y de relevos,
    *   estructura jerárquica para navegación.

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

## 📚 Documentación

La documentación es parte esencial del proyecto y se mantiene **versionada junto al código**.

| Documento                   | Descripción                       |
| --------------------------- | --------------------------------- |
| `INSTALLATION_GUIDE.md`  | Instalación y ejecución           |
| `USER_GUIDE.md`          | Guía de uso para usuarios finales |
| `JSON_CONTRACT.md`       | Especificación técnica del JSON   |
| `TECHNICAL_REFERENCE.md` | Arquitectura y Knowledge Transfer |

> Nota: Los diagramas están escritos en **Mermaid** y se renderizan automáticamente en GitHub/GitLab.  
> En VS Code es necesario instalar una extensión de Mermaid para el preview.

***

## Principios de diseño

*   **No invención de datos**  
    Si un dato no está en el PDF, no se genera.

*   **Estabilidad de identificadores**  
    Los IDs no cambian entre ejecuciones.

*   **Modelo canónico**  
    Separación clara entre dimensiones y resultados.

*   **Relevos desnormalizados**  
    Un resultado por miembro para facilitar análisis.

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

## 📄 Licencia

Este proyecto se distribuye bajo licencia **AGPL‑3.0‑or‑later**.

Consulta el fichero LICENSE para más información.

***

## Contacto / Soporte

Para dudas, problemas o propuestas:

*   abre un **issue** en el repositorio,
*   o documenta el caso con un PDF de ejemplo (si es posible).

***
