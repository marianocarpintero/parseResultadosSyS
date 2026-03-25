# INSTALLATION\_GUIDE.md

## Guía de instalación y ejecución

**Proyecto**: Pacifico – Conversión de resultados deportivos a JSON  
**Audiencia**: Usuarios técnicos básicos, analistas, operadores  
**Sistemas soportados**:

*   Windows (PowerShell)
*   Linux / macOS (shell tipo bash o zsh)

**Versión del documento**: 1.0.0

***

## 1. Objetivo de esta guía

Esta guía explica **cómo preparar el entorno y ejecutar el proyecto** para convertir archivos PDF de resultados deportivos en un fichero JSON estructurado.

Al finalizar esta guía, deberías ser capaz de:

*   comprobar que tienes los requisitos necesarios,
*   ejecutar el programa desde línea de comandos,
*   obtener un fichero JSON válido como salida.

***

## 2. Requisitos previos

### 2.1 Conocimientos necesarios

No es necesario ser desarrollador profesional, pero sí:

*   saber abrir una terminal (PowerShell o terminal),
*   ejecutar comandos básicos,
*   saber moverse entre carpetas.

***

### 2.2 Software necesario

#### ✅ Python

*   **Versión mínima recomendada**: Python **3.10**
*   Compatible con Python 3.10, 3.11 y 3.12

Para comprobar si Python está instalado:

```bash
python --version
```

o, en algunos sistemas:

```bash
python3 --version
```

Si ves algo como:

```text
Python 3.11.6
```

✅ Python está instalado correctamente.

***

#### ❌ Errores comunes

*   `python no se reconoce como un comando`
*   `command not found: python`

➡️ En ese caso, debes instalar Python (ver siguiente sección).

***

## 3. Instalación de Python

### 3.1 Windows (PowerShell)

1.  Descarga Python desde:
    *   <https://www.python.org/downloads/windows/>

2.  Durante la instalación:
    *   ✅ Marca **“Add Python to PATH”**
    *   ✅ Usa la instalación recomendada

3.  Abre una **nueva** ventana de PowerShell y comprueba:

```powershell
python --version
```

***

### 3.2 Linux / macOS (zsh, bash)

En la mayoría de sistemas modernos Python ya está instalado.

#### Ubuntu / Debian:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip
```

#### macOS (con Homebrew):

```bash
brew install python
```

Verifica:

```bash
python3 --version
```

***

## 4. Obtener el proyecto

### 4.1 Estructura esperada

El proyecto debe tener, como mínimo, esta estructura:

```text
project/
├── pdf2json.py
├── pdf2tree/
│   ├── __init__.py
│   ├── parser.py
│   ├── normalize.py
│   └── ...
├── requirements.txt
└── data/
    └── PDFs/
```

> El nombre de las carpetas puede variar, pero **`pdf2json.py` debe existir**.

***

### 4.2 Ubicación recomendada

Coloca el proyecto en una ruta sencilla, por ejemplo:

*   **Windows**
    ```text
    C:\datos\pacifico\
    ```

*   **Linux / macOS**
    ```text
    ~/pacifico/
    ```

Evita rutas con:

*   espacios,
*   acentos,
*   carpetas sincronizadas (OneDrive, Google Drive).

***

## 5. Crear un entorno virtual (recomendado)

Usar un entorno virtual evita conflictos con otros proyectos.

### 5.1 Windows (PowerShell)

Desde la carpeta del proyecto:

```powershell
python -m venv .venv
```

Activar el entorno:

```powershell
.venv\Scripts\Activate.ps1
```

Verás algo como:

```text
(.venv) PS C:\datos\pacifico>
```

***

### 5.2 Linux / macOS (zsh / bash)

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Resultado esperado:

```text
(.venv) usuario@equipo pacifico %
```

***

## 6. Instalación de dependencias

Con el entorno virtual activo:

```bash
pip install -r requirements.txt
```

Esto instalará automáticamente todas las librerías necesarias.

Si no hay errores, la instalación está completa ✅

***

## 7. Preparar los archivos de entrada

### 7.1 PDFs de entrada

*   Coloca los PDFs en una carpeta (por ejemplo `data/PDFs/`)
*   Los PDFs deben contener **resultados oficiales de competiciones**

Ejemplo:

```text
data/PDFs/
├── 2026_01_mayores.pdf
├── 2026_02_menores.pdf
└── 2026_master.pdf
```

***

## 8. Ejecutar el programa

### 8.1 Ejecución básica (un PDF)

Desde la carpeta del proyecto:

```bash
python pdf2json.py data/PDFs/2026_01_mayores.pdf
```

Salida esperada:

*   Se genera un fichero JSON en la carpeta actual.

***

### 8.2 Ejecutar varios PDFs a la vez

#### Windows (PowerShell)

```powershell
python pdf2json.py 2026mad.pdf o python pdf2json.py 2025-2026/*.pdf (si quieres usar patrones)
```

#### Linux / macOS

```bash
python pdf2json.py 2026mad.pdf o python pdf2json.py 2025-2026/*.pdf (si quieres usar patrones)
```

Todos los PDFs se procesan y se combinan en **un único JSON**.

***

## 9. Verificar la salida

Al finalizar la ejecución:

*   debe existir un fichero `.json`,
*   el fichero debe abrirse sin errores,
*   el JSON debe contener al menos:
    *   `meta`
    *   `dimensions`
    *   `results`

Ejemplo rápido de comprobación:

```bash
python -c "import json; json.load(open('output.json'))"
```

Si no hay salida → ✅ JSON válido.

***

## 10. Problemas frecuentes y soluciones

### ❌ El comando `python` no funciona

*   Prueba `python3`
*   Reabre la terminal
*   Reinstala Python asegurándote de marcar *Add to PATH*

***

### ❌ Error instalando dependencias

```text
pip: command not found
```

Solución:

```bash
python -m pip install --upgrade pip
```

***

### ❌ Caracteres raros (ñ, acentos) en Windows

Asegúrate de usar UTF‑8:

```powershell
chcp 65001
```

Y vuelve a ejecutar el comando.

***

## 11. Qué NO cubre esta guía

Esta guía **no explica**:

*   el significado del JSON,
*   cómo interpretar resultados,
*   detalles técnicos del parser.

Para eso existen:

*   `USER_GUIDE.md`
*   `JSON_CONTRACT.md`
*   `TECHNICAL_REFERENCE.md`

***

## 12. Resumen rápido

✅ Instalas Python  
✅ Creas un entorno virtual  
✅ Instalas dependencias  
✅ Ejecutas `pdf2json.py`  
✅ Obtienes un JSON reutilizable
