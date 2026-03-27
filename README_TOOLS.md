# Herramientas auxiliares

Este directorio contiene **herramientas de soporte y testing**.  
No forman parte del flujo normal de ejecución del proyecto.

---

## txt2json – Fixtures de texto

`tools/txt2json.py` permite ejecutar el parser sobre ficheros **`.txt`** que simulan la salida de `extract_text()` de un PDF.

Uso típico:

```bash
python -m tools.txt2json tests/fixtures/text/ddcc_assorted.txt --debug
```

### Importante

* Los .txt NO son una fuente de entrada normal
* Se usan exclusivamente para:

  * Desarrollo
  * Tests
  * Reproducción de casos problemáticos

* El wrapper inyecta automáticamente el flag --allow-txt

Para procesamiento real de datos, usa siempre:

```bash
python jsonResultados.py
```

---
