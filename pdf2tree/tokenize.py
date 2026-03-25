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

from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, Any
import re

from .normalize import normalize_spaces, normalize_dashes

EVENT_TITLE_ES_RE = re.compile(r"^(?:4x)?\d+(?:[.,]\d+)?\s*m\.?\b", re.IGNORECASE)
EVENT_TITLE_ES_START_RE = re.compile(r"^(?:4x)?\d+(?:[.,]\d+)?\s*m\.?\b", re.IGNORECASE)
EVENT_TITLE_MASTER_START_RE = re.compile(r"^lanzamiento\s+de\s+cuerda\b", re.IGNORECASE)
EVENT_TITLE_MASTER_SEX_LETTER_RE = re.compile(r"\bmaster\s+[mfx]\b", re.IGNORECASE)
CAT_ES_RE = re.compile(r"\b(juvenil|junior|júnior|absoluto|absoluta|cadete|infantil|máster|master)\b", re.IGNORECASE)
SEX_ES_RE = re.compile(r"\b(femen\w*|mascul\w*|mixt\w*)\b", re.IGNORECASE)

CAT_ABBR_RE = re.compile(r"\b(cad|inf|juv|jun|abs)\b", re.IGNORECASE)
SEX_LETTER_RE = re.compile(r"\b([mfx])\b", re.IGNORECASE)

AGE_RANGE_RE = re.compile(r"\b\d{2}\s*-\s*\d{2}\b")

TABLE_HEADER_RE = re.compile(r"^\s*Socorrista\s*/\s*Lifeguard\b", re.IGNORECASE)
TABLE_HEADER_ANY_RE = re.compile(r"Socorrista\s*/\s*Lifeguard", re.IGNORECASE)
CATEGORY_SEX_RE = re.compile(r"^\s*(.+?)\s*\((.+?)\)\s*$")
CAT_OK = re.compile(r"\b(infantil|cadete|juvenil|junior|júnior|absoluto|absoluta|m[áa]ster)\b", re.IGNORECASE)
SEX_OK = re.compile(r"\b(femen\w*|mascul\w*|mixt\w*|women|men)\b", re.IGNORECASE)
ROW_START_RE = re.compile(r"^\d+\b")
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
TIME_RE = re.compile(r"\b\d{1,2}:\d{2}:\d{2}\b")
NAME_COMMA_START_RE = re.compile(r"^[^,]{2,},\s*[^,]{2,}\b")
NAME_COMMA_RE = re.compile(r"^[^,]{2,},\s*[^,]{2,}$")  # exactamente 1 coma, 2+ chars a cada lado
HEADER_BAD_WORDS = (
    "campeonato", "championship", "resultados", "final results",
    "socorrista", "lifeguard", "club / team", "club/team",
    "elim.t", "final.t", "ptos", "score",
     "fase territorial", "sesion", "sesión", "jornada", "liga", "menores", "mayores"
)

class TokenType(Enum):
    EVENT_TITLE = auto()
    CATEGORY_LINE = auto()
    TABLE_HEADER = auto()
    INDIVIDUAL_ROW = auto()
    TEAM_ROW = auto()
    RELAY_MEMBER = auto()
    NOISE = auto()
    DATE_POOL = auto()
    COMPETITION_LINE = auto()

@dataclass(frozen=True)
class Token:
    type: TokenType
    page: int
    line_no: int
    raw: str
    norm: str
    meta: Dict[str, Any]

def _has_split_year(parts: list[str]) -> bool:
    # detecta secuencia de 4 tokens de un dígito: 2 0 0 6 / 1 9 9 8 etc.
    for i in range(len(parts) - 3):
        chunk = parts[i:i+4]
        if all(len(x) == 1 and x.isdigit() for x in chunk):
            year = int("".join(chunk))
            if 1900 <= year <= 2099:
                return True
    return False

def _strip_multi_age_ranges(text: str) -> tuple[str, bool]:
    """
    Si hay 2 o más rangos de edad, los elimina del título.
    Devuelve (texto_limpio, multi_age_range)
    """
    ranges = AGE_RANGE_RE.findall(text)
    if len(ranges) < 2:
        return text, False
    cleaned = AGE_RANGE_RE.sub("", text)
    cleaned = re.sub(r"\by\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = normalize_spaces(cleaned)

    return cleaned, True


class Tokenizer:
    """
    Clasifica líneas. NO construye results; solo etiqueta.
    """
    def classify(self, page: int, line_no: int, line: str) -> Token:
        raw = line
        norm = normalize_spaces(line)
        norm_d = normalize_dashes(norm)
        low = norm.lower()

        # ----------------------------------
        # --- CABECERA
        # ----------------------------------
        if TABLE_HEADER_RE.match(norm):
            return Token(TokenType.TABLE_HEADER, page, line_no, raw, norm, {})

        mth = TABLE_HEADER_ANY_RE.search(norm)
        if mth:
            pre_title = norm[:mth.start()].strip(" *")
            return Token(TokenType.TABLE_HEADER, page, line_no, raw, norm, {"pre_title": pre_title})

        # Línea de cabecera con fecha y piscina: no es fila de resultados
        if ("(piscina" in low) or ("pool:" in low):
            return Token(TokenType.DATE_POOL, page, line_no, raw, norm, {})

        # ----------------------------------
        # --- CATEGORÍA
        # ----------------------------------
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

        # Título de prueba con distancia + categoría abreviada + sexo en letra (Cad F / Inf M / etc.)
        if EVENT_TITLE_ES_START_RE.match(norm) and (CAT_ES_RE.search(norm) or CAT_ABBR_RE.search(low)) and SEX_LETTER_RE.search(low) \
        and (not YEAR_RE.search(norm)) and (not TIME_RE.search(norm)):
            clean_norm, multi_age = _strip_multi_age_ranges(norm)
            meta = {}
            if multi_age:
                meta["multi_age_range"] = True
            return Token(
                TokenType.EVENT_TITLE,
                page,
                line_no,
                raw,
                clean_norm,
                meta
            )

        # ----------------------------------
        # --- CABECERA 2
        # ----------------------------------
        # Cabecera de prueba en ES tipo: "50 m. ... categoría juvenil femenino"
        if EVENT_TITLE_ES_RE.match(norm) and ("categor" in low) and (not YEAR_RE.search(norm)) and (not TIME_RE.search(norm)):
            clean_norm, multi_age = _strip_multi_age_ranges(norm)
            meta = {}
            if multi_age:
                meta["multi_age_range"] = True
            return Token(
                TokenType.EVENT_TITLE,
                page,
                line_no,
                raw,
                clean_norm,
                meta
            )

        # Cabecera de prueba en ES tipo: "50 m. ... categoría juvenil femenino" o "Lanzamiento de Cuerda ... categoría junior masculino"
        if (EVENT_TITLE_ES_START_RE.match(norm) or EVENT_TITLE_MASTER_START_RE.match(norm)) \
        and CAT_ES_RE.search(norm) and SEX_ES_RE.search(norm) \
        and (not YEAR_RE.search(norm)) and (not TIME_RE.search(norm)):
            clean_norm, multi_age = _strip_multi_age_ranges(norm)
            meta = {}
            if multi_age:
                meta["multi_age_range"] = True
            return Token(
                TokenType.EVENT_TITLE,
                page,
                line_no,
                raw,
                clean_norm,
                meta
            )

        # Caso especial: títulos "Lanzamiento de cuerda Master M/F" donde el sexo viene en la CATEGORY_LINE siguiente
        if EVENT_TITLE_MASTER_START_RE.match(norm) and CAT_ES_RE.search(norm) and (not YEAR_RE.search(norm)) and (not TIME_RE.search(norm)):
            clean_norm, multi_age = _strip_multi_age_ranges(norm)
            meta = {}
            if multi_age:
                meta["multi_age_range"] = True
            return Token(
                TokenType.EVENT_TITLE,
                page,
                line_no,
                raw,
                clean_norm,
                meta
            )

        # Caso: "Lanzamiento de cuerda Master M/F/X" (sexo en letra), el detalle de rango viene en la CATEGORY_LINE siguiente
        msex = re.search(r"\bmaster\s+([mfx])\b", low)
        if EVENT_TITLE_MASTER_START_RE.match(norm) and msex and (not YEAR_RE.search(norm)) and (not TIME_RE.search(norm)):
            sex_hint = msex.group(1).upper()  # M / F / X
            return Token(TokenType.EVENT_TITLE, page, line_no, raw, norm, {"sex_hint": sex_hint})

        # ----------------------------------
        # --- RESULTADOS
        # ----------------------------------
        # Filas de resultados
        if ROW_START_RE.match(norm):
            parts = norm.split()
            if YEAR_RE.search(norm) or _has_split_year(parts):
                return Token(TokenType.INDIVIDUAL_ROW, page, line_no, raw, norm, {})
            return Token(TokenType.TEAM_ROW, page, line_no, raw, norm, {})

        # TEAM_ROW sin posición (caso típico: falta el "1" en la extracción)
        if (not ROW_START_RE.match(norm)) and (not YEAR_RE.search(norm)) and TIME_RE.search(norm):
            # Heurística: empieza por "APELLIDOS, NOMBRE", trae tiempo, y no es cabecera
            if NAME_COMMA_START_RE.match(norm) and not any(w in low for w in HEADER_BAD_WORDS):
                return Token(TokenType.TEAM_ROW, page, line_no, raw, norm, {"implicit_position": True})

        # Miembro de relevo: normalmente "APELLIDO, NOMBRE" en su propia línea
        if (not ROW_START_RE.match(norm)) and (not YEAR_RE.search(norm)) and (not TIME_RE.search(norm)):
            low = norm_d.lower()
            if re.search(r"\d+\s*[ªº]", norm):
                return Token(TokenType.NOISE, page, line_no, raw, norm, {})
            # Cabeceras tipo "1ª sesión ... , 2ª sesión ..." NO son miembros de relevo aunque tengan coma
            if re.search(r"\d+\s*[ªº]", norm):
                return Token(TokenType.COMPETITION_LINE, page, line_no, raw, norm, {})
            if NAME_COMMA_RE.match(norm) and not any(w in low for w in HEADER_BAD_WORDS):
                # Evitar direcciones/ruido: si hay dígitos, no es un nombre de persona.
                if re.search(r"\d", norm):
                    return Token(TokenType.NOISE, page, line_no, raw, norm, {"reason": "relay_member_has_digits"})
                return Token(TokenType.RELAY_MEMBER, page, line_no, raw, norm, {})

         # ----------------------------------
        # --- CABECERA 3
        # ----------------------------------           
        # Título de prueba (muy permisivo; se confirma al llegar TABLE_HEADER)
        if ("men's" in low) or ("women's" in low) or ("line throw" in low) or ("4x" in low):
            clean_norm, multi_age = _strip_multi_age_ranges(norm)
            meta = {}
            if multi_age:
                meta["multi_age_range"] = True
            return Token(
                TokenType.EVENT_TITLE,
                page,
                line_no,
                raw,
                clean_norm,
                meta
            )

        return Token(TokenType.NOISE, page, line_no, raw, norm, {})

