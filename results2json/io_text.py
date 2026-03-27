# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Mariano Carpintero
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.


# pdf2tree/io_text.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterator, List, Optional

from .normalize import normalize_spaces
from .io_pdf import PageText


_PAGE_RE = re.compile(r"^\s*PAGE\s+(?P<idx>\d+)(?:\s*/\s*(?P<total>\d+))?\s*$", re.IGNORECASE)
_SEP_RE = re.compile(r"^\s*={10,}\s*$")  # línea de =======... (10+)


def iter_text_pages(txt_path: str, *, keep_empty_lines: bool = False) -> Iterator[PageText]:
    """
    Itera un fichero TXT con formato de dump (bloques por página) y produce PageText.

    Formato esperado (típico dump):
        ================================================================================
        PAGE 1/23
        ================================================================================
        línea...
        línea...

        ================================================================================
        PAGE 2/23
        ================================================================================
        ...

    - page_index: número de página detectado en 'PAGE X/Y'
    - text: texto crudo del bloque de página (sin el marcador PAGE ni separadores)
    - lines: lista de líneas normalizadas (normalize_spaces) como hace iter_pdf_pages() [1](https://myoffice.accenture.com/personal/mariano_carpintero_accenture_com/Documents/Microsoft%20Copilot%20Chat%20Files/2026espMaster.pdf)

    Si el fichero no tiene marcadores PAGE, se devolverá una sola página (page_index=1).
    """

    with open(txt_path, "r", encoding="utf-8") as f:
        raw_lines = f.read().splitlines()

    pages: List[tuple[int, List[str]]] = []
    current_page_idx: Optional[int] = None
    current_buf: List[str] = []

    def _flush():
        nonlocal current_page_idx, current_buf
        if current_page_idx is None:
            return
        pages.append((current_page_idx, current_buf))
        current_page_idx = None
        current_buf = []

    i = 0
    while i < len(raw_lines):
        line = raw_lines[i]

        # Detectar marcador de página: "PAGE X/Y"
        m = _PAGE_RE.match(line)
        if m:
            # flush página anterior si existía
            _flush()
            current_page_idx = int(m.group("idx"))
            current_buf = []
            i += 1
            continue

        # Ignorar separadores "=====" (los dumps los ponen antes/después de PAGE)
        if _SEP_RE.match(line):
            i += 1
            continue

        # Si ya estamos dentro de una página, acumulamos líneas
        if current_page_idx is not None:
            current_buf.append(line)
        else:
            # No hemos visto "PAGE ..." todavía.
            # Guardamos como "preámbulo" de página 1 si finalmente no hay marcadores.
            current_buf.append(line)
        i += 1

    # flush final
    if current_page_idx is not None:
        _flush()
    else:
        # No hubo ningún "PAGE X/Y": tratamos todo como una única página 1
        text = "\n".join(current_buf).strip("\n")
        lines = [
            normalize_spaces(l)
            for l in text.split("\n")
            if keep_empty_lines or l.strip()
        ]
        yield PageText(page_index=1, text=text, lines=lines)
        return

    # Emitir páginas detectadas
    for page_idx, buf in sorted(pages, key=lambda x: x[0]):
        text = "\n".join(buf).strip("\n")
        lines = [
            normalize_spaces(l)
            for l in text.split("\n")
            if keep_empty_lines or l.strip()
        ]
        yield PageText(page_index=page_idx, text=text, lines=lines)