from __future__ import annotations

import re
import unicodedata
from typing import Optional, Tuple


def normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def normalize_pool(pool_raw: str) -> str:
    pool_raw = pool_raw.replace(" ", "").upper()
    if pool_raw in {"25M", "25E", "50M", "50E"}:
        return pool_raw
    return ""


def normalize_dashes(s: str) -> str:
    # normaliza guiones unicode a "-"
    return re.sub(r"[‐‑‒–—−]", "-", s)


def normalize_key(s: str) -> str:
    s = normalize_spaces(s)
    return strip_accents(s).lower()


def slugify(s: str) -> str:
    s = normalize_key(s)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "na"


def normalize_title(s: str) -> str:
    """Title Case controlado (mantiene romanos)."""
    if not s:
        return ""
    out = []
    for w in s.split():
        if re.fullmatch(r"[IVXLCDM]+", w.upper()):
            out.append(w.upper())
        else:
            out.append(w.capitalize())
    return " ".join(out)


# ---- tiempo ----
TIME_RAW_RE = re.compile(r"^\d{1,2}:\d{2}:\d{2}$")      # mm:ss:cc
TIME_RAW_DOT_RE = re.compile(r"^\d{1,2}:\d{2}\.\d{1,3}$")  # mm:ss.mmm


def time_raw_to_display_seconds(raw: str) -> Tuple[Optional[str], Optional[float]]:
    """
    raw:
      - '00:31:93'  (mm:ss:cc)
      - '00:31.930' (mm:ss.mmm)
    display:
      - '00:31.930'
    seconds:
      - 31.93
    """
    if not raw:
        return None, None
    raw = raw.strip()

    if TIME_RAW_RE.match(raw):
        mm, ss, cc = raw.split(":")
        mm_i = int(mm)
        ss_i = int(ss)
        cc_i = int(cc)
        ms = cc_i * 10
        display = f"{mm_i:02d}:{ss_i:02d}.{ms:03d}"
        seconds = mm_i * 60 + ss_i + cc_i / 100.0
        return display, seconds

    if TIME_RAW_DOT_RE.match(raw):
        mm, rest = raw.split(":")
        ss, mmm = rest.split(".")
        mm_i = int(mm)
        ss_i = int(ss)
        mmm_i = int(mmm.ljust(3, "0")[:3])
        display = f"{mm_i:02d}:{ss_i:02d}.{mmm_i:03d}"
        seconds = mm_i * 60 + ss_i + (mmm_i / 1000.0)
        return display, seconds

    # fallback: no es tiempo
    return raw, None


# ---- categoría/sexo/status ----
def normalize_category(raw: str) -> Optional[str]:
    if not raw:
        return None
    r = raw.lower()
    if "juvenil" in r:
        return "juvenil"
    # cubre junior/júnior y mojibake tipo j·nior => contiene "nior"
    if "junior" in r or "júnior" in r or "nior" in r:
        return "junior"
    if "absoluta" in r or "absoluto" in r:
        return "absoluto"
    return None


def normalize_sex(raw: str) -> Optional[str]:
    if not raw:
        return None
    r = raw.lower()
    if "women" in r or "fem" in r:
        return "f"
    if "men" in r or "masc" in r:
        return "m"
    if "mixt" in r:
        return "x"
    return None


def parse_status(line: str) -> str:
    u = line.upper()
    if "DESCALIFIC" in u or "DSQ" in u:
        return "DSQ"
    if "NO PRESENTAD" in u or "DNS" in u:
        return "DNS"
    if "NO FINALIZA" in u or "DNF" in u:
        return "DNF"
    if "BAJA" in u:
        return "BAJA"
    return "OK"