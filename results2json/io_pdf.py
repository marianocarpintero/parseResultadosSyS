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


from __future__ import annotations

import pdfplumber
from dataclasses import dataclass
from typing import Iterator, List, Optional, Tuple

from .normalize import normalize_spaces


@dataclass(frozen=True)
class PageText:
    page_index: int
    text: str
    lines: List[str]


def iter_pdf_pages(input_path: str) -> Iterator[PageText]:
    """
    Recorre páginas y devuelve extract_text() + líneas normalizadas.
    """
    with pdfplumber.open(input_path) as pdf:
        for idx, page in enumerate(pdf.pages, start=1):
            txt = page.extract_text() or ""
            lines = [normalize_spaces(l) for l in txt.split("\n") if l.strip()]
            yield PageText(page_index=idx, text=txt, lines=lines)


def dump_extract_text(input_path: str, out_path: str, mode: str = "w") -> None:
    """
    Vuelca EXACTAMENTE lo que devuelve extract_text() por página.
    mode:
      - "w": sobrescribe (por defecto)
      - "a": añade al final (para concatenar varios PDFs)
    """
    with open(out_path, mode, encoding="utf-8") as out:
        with pdfplumber.open(input_path) as pdf:
            for idx, page in enumerate(pdf.pages, start=1):
                txt = page.extract_text() or ""
                out.write("\n" + "=" * 80 + "\n")
                out.write(f"PAGE {idx}/{len(pdf.pages)}\n")
                out.write("=" * 80 + "\n")
                out.write(txt)
                out.write("\n")