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


def iter_pdf_pages(pdf_path: str) -> Iterator[PageText]:
    """
    Recorre páginas y devuelve extract_text() + líneas normalizadas.
    """
    with pdfplumber.open(pdf_path) as pdf:
        for idx, page in enumerate(pdf.pages, start=1):
            txt = page.extract_text() or ""
            lines = [normalize_spaces(l) for l in txt.split("\n") if l.strip()]
            yield PageText(page_index=idx, text=txt, lines=lines)


def dump_extract_text(pdf_path: str, out_path: str, mode: str = "w") -> None:
    """
    Vuelca EXACTAMENTE lo que devuelve extract_text() por página.
    mode:
      - "w": sobrescribe (por defecto)
      - "a": añade al final (para concatenar varios PDFs)
    """
    with open(out_path, mode, encoding="utf-8") as out:
        with pdfplumber.open(pdf_path) as pdf:
            for idx, page in enumerate(pdf.pages, start=1):
                txt = page.extract_text() or ""
                out.write("\n" + "=" * 80 + "\n")
                out.write(f"PAGE {idx}/{len(pdf.pages)}\n")
                out.write("=" * 80 + "\n")
                out.write(txt)
                out.write("\n")