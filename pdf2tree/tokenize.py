from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, Any
import re

from .normalize import normalize_spaces, normalize_dashes

EVENT_TITLE_ES_RE = re.compile(r"^(?:4x)?\d+(?:[.,]\d+)?\s*m\.?\b", re.IGNORECASE)
EVENT_TITLE_ES_START_RE = re.compile(r"^(?:4x)?\d+(?:[.,]\d+)?\s*m\.?\b", re.IGNORECASE)
EVENT_TITLE_MASTER_START_RE = re.compile(r"^lanzamiento\s+de\s+cuerda\b", re.IGNORECASE)
CAT_ES_RE = re.compile(r"\b(juvenil|junior|júnior|absoluto|absoluta|cadete|infantil|máster|master)\b", re.IGNORECASE)
SEX_ES_RE = re.compile(r"\b(femen\w*|mascul\w*|mixt\w*)\b", re.IGNORECASE)
TABLE_HEADER_RE = re.compile(r"^\s*Socorrista\s*/\s*Lifeguard\b", re.IGNORECASE)
TABLE_HEADER_ANY_RE = re.compile(r"Socorrista\s*/\s*Lifeguard", re.IGNORECASE)
CATEGORY_SEX_RE = re.compile(r"^\s*(.+?)\s*\((.+?)\)\s*$")
CAT_OK = re.compile(r"\b(infantil|cadete|juvenil|junior|júnior|absoluto|absoluta|m[áa]ster)\b", re.IGNORECASE)
SEX_OK = re.compile(r"\b(femen\w*|mascul\w*|mixt\w*|women|men)\b", re.IGNORECASE)
ROW_START_RE = re.compile(r"^\d+\b")
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
TIME_RE = re.compile(r"\b\d{1,2}:\d{2}:\d{2}\b")
NAME_COMMA_RE = re.compile(r"^[^,]{2,},\s*[^,]{2,}$")  # exactamente 1 coma, 2+ chars a cada lado
HEADER_BAD_WORDS = (
    "campeonato", "championship", "resultados", "final results",
    "socorrista", "lifeguard", "club / team", "club/team",
    "elim.t", "final.t", "ptos", "score"
)

class TokenType(Enum):
    EVENT_TITLE = auto()
    CATEGORY_LINE = auto()
    TABLE_HEADER = auto()
    INDIVIDUAL_ROW = auto()
    TEAM_ROW = auto()
    RELAY_MEMBER = auto()
    NOISE = auto()

@dataclass(frozen=True)
class Token:
    type: TokenType
    page: int
    line_no: int
    raw: str
    norm: str
    meta: Dict[str, Any]

class Tokenizer:
    """
    Clasifica líneas. NO construye results; solo etiqueta.
    """
    def classify(self, page: int, line_no: int, line: str) -> Token:
        raw = line
        norm = normalize_spaces(line)
        norm_d = normalize_dashes(norm)
        low = norm_d.lower()

        if TABLE_HEADER_RE.match(norm):
            return Token(TokenType.TABLE_HEADER, page, line_no, raw, norm, {})

        mth = TABLE_HEADER_ANY_RE.search(norm)
        if mth:
            pre_title = norm[:mth.start()].strip(" *")
            return Token(TokenType.TABLE_HEADER, page, line_no, raw, norm, {"pre_title": pre_title})

        m = CATEGORY_SEX_RE.match(norm)
        if m:
            cat_raw = m.group(1)
            sex_raw = m.group(2)
            if CAT_OK.search(cat_raw) and SEX_OK.search(sex_raw):
                return Token(TokenType.CATEGORY_LINE, page, line_no, raw, norm, {
                    "cat_raw": cat_raw,
                    "sex_raw": sex_raw
                })
            # si no pasa validación, NO es category_line

        # Cabecera de prueba en ES tipo: "50 m. ... categoría juvenil femenino"
        if EVENT_TITLE_ES_RE.match(norm) and ("categor" in low) and (not YEAR_RE.search(norm)) and (not TIME_RE.search(norm)):
            return Token(TokenType.EVENT_TITLE, page, line_no, raw, norm, {})

        # Cabecera de prueba en ES tipo: "50 m. ... categoría juvenil femenino" o "Lanzamiento de Cuerda ... categoría junior masculino"
        if (EVENT_TITLE_ES_START_RE.match(norm) or EVENT_TITLE_MASTER_START_RE.match(norm)) \
        and CAT_ES_RE.search(norm) and SEX_ES_RE.search(norm) \
        and (not YEAR_RE.search(norm)) and (not TIME_RE.search(norm)):
            return Token(TokenType.EVENT_TITLE, page, line_no, raw, norm, {})

        # Filas de resultados
        if ROW_START_RE.match(norm):
            parts = norm.split()
            if YEAR_RE.search(norm) or self._has_split_year(parts):
                return Token(TokenType.INDIVIDUAL_ROW, page, line_no, raw, norm, {})
            return Token(TokenType.TEAM_ROW, page, line_no, raw, norm, {})

        # Miembro de relevo: normalmente "APELLIDO, NOMBRE" en su propia línea
        if (not ROW_START_RE.match(norm)) and (not YEAR_RE.search(norm)) and (not TIME_RE.search(norm)):
            low = norm_d.lower()
            if NAME_COMMA_RE.match(norm) and not any(w in low for w in HEADER_BAD_WORDS):
                return Token(TokenType.RELAY_MEMBER, page, line_no, raw, norm, {})
            
        # Título de prueba (muy permisivo; se confirma al llegar TABLE_HEADER)
        if ("men's" in low) or ("women's" in low) or ("line throw" in low) or ("4x" in low):
            return Token(TokenType.EVENT_TITLE, page, line_no, raw, norm, {})

        return Token(TokenType.NOISE, page, line_no, raw, norm, {})

    def _has_split_year(self, parts: list[str]) -> bool:
        # detecta secuencia de 4 tokens de un dígito: 2 0 0 6 / 1 9 9 8 etc.
        for i in range(len(parts) - 3):
            chunk = parts[i:i+4]
            if all(len(x) == 1 and x.isdigit() for x in chunk):
                year = int("".join(chunk))
                if 1900 <= year <= 2099:
                    return True
        return False
    