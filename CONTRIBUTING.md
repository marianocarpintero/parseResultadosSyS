# CONTRIBUTING.md

## Contributing to Pacifico

Gracias por tu interés en contribuir a **Pacifico** 🎉  
Este documento describe **cómo colaborar de forma efectiva**, manteniendo la calidad, estabilidad y coherencia del proyecto.

***

## Alcance del proyecto

Pacifico es un **parser determinista y normalizador** de resultados deportivos en PDF que genera un **JSON canónico estable**.

Las contribuciones más habituales incluyen:

*   soporte para nuevos formatos de PDF,
*   mejoras en reglas de normalización,
*   corrección de edge cases reales,
*   mejoras de documentación,
*   refactor técnico sin cambio funcional.

***

## Requisitos antes de contribuir

Antes de empezar, por favor revisa:

*   `README.md`
*   `JSON_CONTRACT.md`
*   `TECHNICAL_REFERENCE.md`

Estos documentos definen:

*   el **contrato de datos**,
*   los **principios de diseño**,
*   las **reglas que no deben romperse**.

***

## Principios que deben respetarse

Cualquier contribución **DEBE** cumplir estos principios:

1.  **No invención de datos**  
    Si un dato no está explícitamente en el PDF, no se genera.

2.  **Idempotencia**  
    Reprocesar los mismos PDFs debe producir el mismo JSON.

3.  **Estabilidad de IDs**  
    No se deben cambiar reglas de generación de identificadores sin versionar el contrato.

4.  **Compatibilidad hacia atrás**  
    Los campos existentes no se eliminan ni se reutilizan con otro significado.

***

## Tipos de contribuciones

### Corrección de errores

*   Incluye siempre:
    *   PDF(s) de ejemplo (si es posible),
    *   descripción clara del problema,
    *   resultado esperado vs real.

***

### Soporte para nuevos formatos de PDF

*   Ajusta **parsers**, no el modelo.
*   Normalmente implica cambios en:
    *   `HeaderParser`
    *   `RowParser`
*   Documenta el nuevo caso en:
    *   `TECHNICAL_REFERENCE.md` (Anexo E si es edge case).

***

### Nuevas reglas de normalización

*   Deben ser:
    *   deterministas,
    *   idempotentes,
    *   no destructivas.
*   Si afectan a la salida JSON:
    *   actualiza `JSON_CONTRACT.md`.

***

### Cambios en deduplicación o remapeo

**Cambios críticos**

Antes de enviar un PR:

*   abre un **issue** para discutir el impacto,
*   evalúa impacto histórico,
*   considera versionado del contrato.

***

## Flujo de trabajo recomendado

1.  Haz un fork del repositorio
2.  Crea una rama descriptiva:
    ```text
    feature/soporte-nuevo-pdf
    fix/ocr-club-names
    docs/expand-json-contract
    ```
3.  Realiza cambios pequeños y enfocados
4.  Actualiza la documentación si aplica
5.  Abre un Pull Request

***

## Checklist para Pull Requests

Antes de abrir un PR, verifica:

*   [ ] El parser sigue siendo idempotente
*   [ ] Los IDs no cambian para datos existentes
*   [ ] No se rompe el contrato JSON
*   [ ] La documentación está actualizada
*   [ ] El cambio está justificado con un caso real

***

## Comunicación

*   Usa **Issues** para bugs, propuestas y discusiones técnicas
*   Usa PRs solo cuando el diseño esté claro
*   Sé explícito y técnico: este es un proyecto orientado a datos

***

Gracias por contribuir a Pacifico  
Cada mejora ayuda a que los datos sean más fiables y reutilizables.

***
