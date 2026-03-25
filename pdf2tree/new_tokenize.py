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


import re
from dataclasses import dataclass
from typing import List


@dataclass
class Token:
    type: str
    value: str


# ---------- REGEX ----------

RE_NOISE = re.compile(
    r"(clasificación general|resultados|página\s+\d+)",
    re.IGNORECASE
)

HEADER_EVENT = "HEADER_EVENT"
HEADER_CATEGORY = "HEADER_CATEGORY"

RE_POSITION = re.compile(r"^\s*(\d{1,3})\s+")
RE_RESULT_TIME = re.compile(r"(\d{1,2}:)?\d{1,2}\.\d{2,3}")

RE_RELAY_COUNT = re.compile(r"\b(\d+)\s*[xX]\b")
RE_DISTANCE = re.compile(r"\b\d+\s*m\b", re.IGNORECASE)

RE_AGE_RANGE = re.compile(r"\b\d{2}\s*-\s*\d{2}\b")
RE_GENDER = re.compile(r"\b(Masculino|Femenino|Mixto)\b", re.IGNORECASE)

CATEGORIES = [
    "Infantil", "Cadete", "Juvenil", "Junior", "Absoluto", "Master"
]

STYLES = [
    "remolque de maniquí con aletas",
    "remolque de maniquí",
    "arrastre de maniquí",
    "socorrista",
    "supersocorrista",
    "obstáculos",
    "combinada"
]

STYLE_PATTERNS = [
    re.compile(rf"\b{re.escape(style)}\b", re.IGNORECASE)
    for style in STYLES
]

# Helpers
def is_header_event(tokens):
    has_distance = any(t.type == "DISTANCE" for t in tokens)
    has_style = any(t.type == "STYLE" for t in tokens)
    has_result = any(t.type == "RESULT_TIME" for t in tokens)
    has_position = any(t.type == "POSITION" for t in tokens)
    has_athlete = any(t.type == "ATHLETE" for t in tokens)

    return has_distance and has_style and not (
        has_result or has_position or has_athlete
    )

def is_header_event(tokens):
    return (
        any(t.type == "DISTANCE" for t in tokens)
        and any(t.type == "STYLE" for t in tokens)
        and not any(t.type in ("POSITION", "RESULT_TIME") for t in tokens)
    )


def is_header_category(tokens):
    return (
        any(t.type == "CATEGORY" for t in tokens)
        and not any(t.type in ("DISTANCE", "RESULT_TIME", "POSITION") for t in tokens)
    )

# Tokenización de una línea
def tokenize_line(line: str) -> List[Token]:
    tokens: List[Token] = []
    text = line.strip()

    if not text:
        return tokens

    if RE_NOISE.search(text):
        return tokens

# Posición
    m = RE_POSITION.match(line)
    if m:
        tokens.append(Token("POSITION", m.group(1)))
        line = line[m.end():]

# Result Time
    for m in RE_RESULT_TIME.finditer(line):
        tokens.append(Token("RESULT_TIME", m.group(0)))

# Relay
    for m in RE_RELAY_COUNT.finditer(text):
        tokens.append(Token("RELAY_COUNT", m.group(1)))
    
# Distance
    for m in RE_DISTANCE.finditer(text):
            tokens.append(Token("DISTANCE", m.group(0).lower()))

# Category / Age-Range / Gender
    for cat in CATEGORIES:
        if re.search(rf"\b{cat}\b", text, re.IGNORECASE):
            tokens.append(Token("CATEGORY", cat))
            break

    for m in RE_AGE_RANGE.finditer(text):
        tokens.append(Token("AGE_RANGE", m.group(0)))

    for m in RE_GENDER.finditer(text):
        g = m.group(1).lower()
        tokens.append(Token("GENDER", "M" if g.startswith("m") else "F" if g.startswith("f") else "X"))

# Style
    for style in STYLES:
        if re.search(rf"\b{style}\b", text, re.IGNORECASE):
            tokens.append(Token("STYLE", style))
    
# --- HEADER DETECTION ---
    if is_header_event(tokens):
        return [Token("HEADER_EVENT", line.strip())]

    if is_header_category(tokens):
        return [Token("HEADER_CATEGORY", line.strip())]

    return tokens