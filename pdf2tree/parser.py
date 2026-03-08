from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, List, Dict, Any, Callable, Tuple
from .events import build_event_fields

from .tokenize import Token, TokenType
from .normalize import (
    normalize_category,
    normalize_sex,
    normalize_key,
    normalize_athlete_name,
    parse_status,
    slugify,
    time_raw_to_display_seconds,
)
from .schema import Event, Result, TimeInfo, Labels, Club, Athlete
from .trace import TraceSink, NullTrace


# Regex robustos
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
TIME_RE = re.compile(r"\b\d{1,2}:\d{2}:\d{2}\b")
CATEGORY_LINE_RE = re.compile(r"^\s*(.+?)\s*\((.+?)\)\s*$", re.IGNORECASE)
CLUB_START_TOKENS = {"club", "c.d.", "c.d.e", "cde", "c.n.", "cn", "real", "asociación", "asociacion"}


class State(Enum):
    SEEK_TABLE = auto()
    IN_RESULTS = auto()
    IN_RELAY_MEMBERS = auto()


@dataclass
class PendingHeader:
    title: Optional[str] = None
    category_line: Optional[str] = None
    last_full_title: Optional[str] = None


@dataclass
class RelayContext:
    club_id: str
    club_name: str
    position: Optional[int]
    status: str
    time_raw: Optional[str]
    points: Optional[int]
    expected_size: int
    members: List[str] = field(default_factory=list)


@dataclass
class ParseContext:
    state: State = State.SEEK_TABLE
    pending: PendingHeader = field(default_factory=PendingHeader)
    current_event_id: Optional[str] = None
    current_event_discipline: Optional[str] = None
    current_event_relay: bool = False
    relay_ctx: Optional[RelayContext] = None


class SinglePassParser:
    """
    Parser single-pass, orientado a trazabilidad:
    - Commit de evento al ver TABLE_HEADER
    - Relays: TEAM_ROW abre contexto; RELAY_MEMBER añade; flush al llegar a expected_size
    - Individual: INDIVIDUAL_ROW emite atleta/club/result
    """

    def __init__(
        self,
        trace: Optional[TraceSink] = None,
        on_event: Optional[Callable[[Event], None]] = None,
        on_result: Optional[Callable[[Result], None]] = None,
        on_club: Optional[Callable[[Club], None]] = None,
        on_athlete: Optional[Callable[[Athlete], None]] = None,
        club_filters=None,
    ) -> None:
        self.ctx = ParseContext()
        self.trace = trace or NullTrace()
        self.on_event = on_event
        self.on_result = on_result
        self.on_club = on_club
        self.on_athlete = on_athlete
        self.club_filters_norm = [normalize_key(x) for x in (club_filters or [])if x]

    # -----------------------
    # Helpers: emit dimensions
    # -----------------------
    def _emit_club(self, club_id: str, club_name: str) -> None:
        if callable(self.on_club):
            self.on_club(Club(id=club_id, name=club_name, slug=slugify(club_name)))
        self.trace.emit({"action": "EMIT_CLUB", "club_id": club_id, "club_name": club_name})

    def _emit_athlete(self, athlete_id: str, name: str, birth_year: Optional[int]) -> None:
        if callable(self.on_athlete):
            self.on_athlete(Athlete(id=athlete_id, name=name, birth_year=birth_year))
        self.trace.emit({"action": "EMIT_ATHLETE", "athlete_id": athlete_id, "name": name, "birth_year": birth_year})

    def _clean_club_tail(self, club_name: str) -> str:
        # quita "(juvenil)" "(absoluta)" etc. al final
        return re.sub(r"\s*\([^()]*\)\s*$", "", club_name or "").strip()

    def _parse_points_from_tokens(self, parts: List[str]) -> Optional[int]:
        for t in reversed(parts):
            if t.isdigit():
                v = int(t)
                if v < 1000:
                    return v
        return None

    def _club_passes(self, club_name: str) -> bool:
        if not self.club_filters_norm:
            return True
        ck = normalize_key(club_name)
        return any(f in ck for f in self.club_filters_norm)


    # -----------------------
    # Event commit (A/B/C)
    # -----------------------
    def _commit_event_on_table(self) -> None:
        title = self.ctx.pending.title
        catline = self.ctx.pending.category_line
        last_title = self.ctx.pending.last_full_title
        use_title = title or last_title or "unknown"

        if title:
            self.ctx.pending.last_full_title = title

        fields = build_event_fields(use_title, catline)

#        existing = None
#        if callable(self.on_event) and hasattr(self.on_event, "__self__"):
#            b = self.on_event.__self__
#            if hasattr(b, "events"):
#                existing = b.events.get(fields["id"])

        dbg = fields.get("debug_info")
        if dbg:
            self.trace.emit({"action": "DEBUG_EVENT_FIELDS", "debug": dbg})

        self.ctx.current_event_id = fields["id"]
        self.ctx.current_event_discipline = fields["base"]
        self.ctx.current_event_relay = fields["relay"]

        # emitir Event a dimensions
        if callable(self.on_event):
            self.on_event(Event(
                id=fields["id"],
                base=fields["base"],
                discipline=fields["base"],
                category=fields["category_display"],
                sex=fields["sex"],           # ya es F/M/X
                relay=fields["relay"],
                distance_m=fields["distance_m"],
            ))

        self.ctx.pending.title = None
        self.ctx.pending.category_line = None
        self.ctx.state = State.IN_RESULTS

    # -----------------------
    # Row parsing
    # -----------------------
    def _open_relay_from_team_row(self, line: str) -> None:
        parts = line.split()
        position = int(parts[0]) if parts and parts[0].isdigit() else None

        status = parse_status(line)
        times = TIME_RE.findall(line)
        time_raw = times[-1] if times else None

        points = self._parse_points_from_tokens(parts)

        cut_idx = len(parts)
        for i, t in enumerate(parts):
            if TIME_RE.fullmatch(t):
                cut_idx = i
                break
            tl = t.lower()
            # cortar por estados en 1 token (Descalificado/Baja/DNS/DNF)
            if tl in {"descalificado", "baja", "dns", "dnf"}:
                cut_idx = i
                break
            # cortar por "No Finaliza" / "No Presentado"
            if tl == "no" and i + 1 < len(parts):
                nxt = parts[i+1].lower()
                if nxt in {"finaliza", "presentado"}:
                    cut_idx = i
                    break

        club_start = 1
        for i in range(1, min(len(parts), cut_idx)):
            if parts[i].lower() in CLUB_START_TOKENS:
                club_start = i
                break

        # 1er miembro del relevo: tokens entre posición y el inicio del club
        first_member = ""
        if club_start > 1:
            first_member = " ".join(parts[1:club_start]).strip()
        # Limpieza mínima: si por alguna razón queda vacío, lo ignoramos
        # (si el PDF NO trae atleta en la primera línea, first_member quedará "")

        if first_member:
            first_member = normalize_athlete_name(first_member)

        club_name_raw= " ".join(parts[club_start:cut_idx]).strip()
        club_name = self._clean_club_tail(club_name_raw) or "club_unknown"
        # filtro de clubes
        if not self._club_passes(club_name):
            self.trace.emit({"action": "SKIP_TEAM_ROW_BY_CLUB", "club": club_name, "filter": self.club_filters_norm})
            # IMPORTANTÍSIMO: NO entrar en IN_RELAY_MEMBERS => así los RELAY_MEMBER siguientes se ignoran
            return        
        club_id = "club_" + slugify(club_name)

        # emitir club
        self._emit_club(club_id, club_name)

        disc_l = (self.ctx.current_event_discipline or "").lower()
        expected_size = 2 if ("lanzamiento" in disc_l or "line throw" in disc_l) else 4

        self.ctx.relay_ctx = RelayContext(
            club_id=club_id,
            club_name=club_name,
            position=position,
            status=status,
            time_raw=time_raw,
            points=points,
            expected_size=expected_size,
            members=[first_member] if first_member else []
        )

        self.ctx.state = State.IN_RELAY_MEMBERS

        self.trace.emit({
            "action": "OPEN_RELAY",
            "event_id": self.ctx.current_event_id,
            "club": club_name,
            "expected_size": expected_size,
            "status": status,
            "time_raw": time_raw,
            "points": points,
        })

    def _flush_relay_context(self, competition_id: str, season_id: str, date: str, reason: str) -> None:
        ctx = self.ctx.relay_ctx
        if not ctx:
            return

        if not self.ctx.current_event_id:
            self.trace.emit({"action": "WARN_FLUSH_RELAY_WITHOUT_EVENT", "reason": reason})
            self.ctx.relay_ctx = None
            return

        discipline = self.ctx.current_event_discipline or ""
        label_x = f"{date}\n{discipline}"
        display, seconds = time_raw_to_display_seconds(ctx.time_raw or "")

        self.trace.emit({
            "action": "FLUSH_RELAY",
            "reason": reason,
            "event_id": self.ctx.current_event_id,
            "club": ctx.club_name,
            "members_count": len(ctx.members),
            "expected_size": ctx.expected_size,
        })

        members = ctx.members if ctx.members else ["Relevos"]
        for member_name in members:
            member_name = normalize_athlete_name(member_name) if member_name != "Relevos" else "Relevos"
            athlete_id = "a_" + slugify(member_name) + "_na"
            # emitir atleta (relay sin año)
            self._emit_athlete(athlete_id, member_name, None)

            rid = "r_" + slugify(f"{competition_id}_{self.ctx.current_event_id}_{athlete_id}")
            r = Result(
                id=rid,
                date=date,
                season_id=season_id,
                competition_id=competition_id,
                event_id=self.ctx.current_event_id,
                athlete_id=athlete_id,
                club_id=ctx.club_id,
                time=TimeInfo(display=display, seconds=seconds, raw=ctx.time_raw),
                status=ctx.status,
                position=ctx.position,
                points=ctx.points,
                series_type="Final",
                labels=Labels(x=label_x),
            )
            if callable(self.on_result):
                self.on_result(r)

        self.ctx.relay_ctx = None

    def _handle_individual_row(self, line: str, competition_id: str, season_id: str, date: str) -> None:
        """
        Parse individual row:
        'pos NOMBRE... 2006 CLUB... 00:12:34 99'
        """
        if not self.ctx.current_event_id:
            self.trace.emit({"action": "WARN_INDIVIDUAL_WITHOUT_EVENT", "text": line})
            return

        parts = line.split()
        if not parts or not parts[0].isdigit():
            self.trace.emit({"action": "ROW_PARSE_FAIL_INDIVIDUAL", "text": line})
            return

        # año
        yidx, ylen, year = self._find_year_in_parts(parts)
        if yidx is None:
            self.trace.emit({"action": "ROW_PARSE_FAIL_INDIVIDUAL_NO_YEAR", "text": line})
            return

        position = int(parts[0])

        raw_name = " ".join(parts[1:yidx]).strip()
        athlete_name = normalize_athlete_name(raw_name)

        birth_year = year
        status = parse_status(line)
        times = TIME_RE.findall(line)
        points = self._parse_points_from_tokens(parts)

        # y el club empieza en yidx + ylen
        club_start_idx = yidx + ylen

        cut_idx = len(parts)
        for i in range(yidx + 1, len(parts)):
            t = parts[i]
            if TIME_RE.fullmatch(t):
                cut_idx = i
                break
            tl = t.lower()
            if tl in {"descalificado", "baja", "dns", "dnf"}:
                cut_idx = i
                break

        club_tokens = parts[club_start_idx:cut_idx]
        # quitar puntos del club si se colaron
        if club_tokens and club_tokens[-1].isdigit():
            v = int(club_tokens[-1])
            if v < 1000:
                club_tokens = club_tokens[:-1]

        club_name = self._clean_club_tail(" ".join(club_tokens).strip()) or "club_unknown"
        # filtro de clubes
        if not self._club_passes(club_name):
            self.trace.emit({"action": "SKIP_INDIVIDUAL_BY_CLUB", "club": club_name, "filter": self.club_filters_norm})
            return        
        club_id = "club_" + slugify(club_name)

        self._emit_club(club_id, club_name)

        athlete_id = "a_" + slugify(athlete_name) + f"_{birth_year}"
        self._emit_athlete(athlete_id, athlete_name, birth_year)

        # tiempos: 2 => preliminar+final; 1 => final; 0 => status
        if len(times) >= 2:
            time_pairs = [("Serie Preliminar", times[0]), ("Final", times[1])]
        elif len(times) == 1:
            time_pairs = [("Final", times[0])]
        else:
            time_pairs = [("Final", None)]

        discipline = self.ctx.current_event_discipline or ""
        label_x = f"{date}\n{discipline}"

        for series_type, t_raw in time_pairs:
            display, seconds = time_raw_to_display_seconds(t_raw or "")
            rid = "r_" + slugify(f"{competition_id}_{self.ctx.current_event_id}_{athlete_id}_{series_type}")

            r = Result(
                id=rid,
                date=date,
                season_id=season_id,
                competition_id=competition_id,
                event_id=self.ctx.current_event_id,
                athlete_id=athlete_id,
                club_id=club_id,
                time=TimeInfo(display=display, seconds=seconds, raw=t_raw),
                status=status,
                position=position,
                points=points,
                series_type=series_type,
                labels=Labels(x=label_x),
            )
            if callable(self.on_result):
                self.on_result(r)

    def _find_year_in_parts(self, parts: List[str]) -> tuple[Optional[int], int, Optional[int]]:
        """
        Devuelve (yidx, ylen, year)
        - yidx: índice donde empieza el año
        - ylen: longitud en tokens del año (1 si normal, 4 si split)
        - year: año int (None si no hay)
        """
        # año normal: un token 2006
        for i in range(1, min(len(parts), 30)):
            if re.fullmatch(r"(19\d{2}|20\d{2})", parts[i]):
                return i, 1, int(parts[i])

        # año split: 2 0 0 6
        for i in range(1, min(len(parts) - 3, 30)):
            chunk = parts[i:i+4]
            if all(len(x) == 1 and x.isdigit() for x in chunk):
                year = int("".join(chunk))
                if 1900 <= year <= 2099:
                    return i, 4, year

        return None, 0, None

    def _looks_like_person_name(self, s: str) -> bool:
        s = (s or "").strip()
        if s.count(",") != 1:
            return False
        if re.search(r"\d", s):  # no números en un nombre
            return False
        low = normalize_key(s)
        # palabras típicas de cabecera/títulos
        bad = ("campeonato", "resultados", "socorrista", "lifeguard", "final results")
        if any(w in low for w in bad):
            return False
        # demasiado largo suele ser título, no persona (ajusta si quieres)
        if len(s) > 60:
            return False
        return True


    # -----------------------
    # Public API
    # -----------------------
    def consume(self, token: Token, *, competition_id: str, season_id: str, date: str) -> None:
        self.trace.emit({
            "page": token.page,
            "line": token.line_no,
            "token": token.type.name,
            "state": self.ctx.state.name,
            "text": token.norm,
            "event_id": self.ctx.current_event_id,
        })

        if token.type == TokenType.EVENT_TITLE:
            # si hay relevo abierto, lo cerramos antes de cambiar de prueba
            if self.ctx.relay_ctx:
                self._flush_relay_context(competition_id, season_id, date, reason="new_event_title")
                self.ctx.state = State.IN_RESULTS
            self.ctx.pending.title = token.norm
            return

        if token.type == TokenType.CATEGORY_LINE:
            self.ctx.pending.category_line = token.norm
            return

        if token.type == TokenType.TABLE_HEADER:
            # flush defensivo si quedó relay abierto
            if self.ctx.relay_ctx:
                self._flush_relay_context(competition_id, season_id, date, reason="table_header")

            pre = token.meta.get("pre_title")
            if pre:
                self.ctx.pending.title = pre

            # SIEMPRE commit aquí
            self._commit_event_on_table()
            return
        
        if token.type == TokenType.TEAM_ROW:
            if self.ctx.state != State.IN_RESULTS:
                return
            if self.ctx.relay_ctx:
                self._flush_relay_context(competition_id, season_id, date, reason="new_team_row")
            self._open_relay_from_team_row(token.norm)
            return

        if token.type == TokenType.RELAY_MEMBER and self.ctx.state == State.IN_RELAY_MEMBERS:
            if not self.ctx.relay_ctx:
                self.trace.emit({"action": "WARN_RELAY_MEMBER_WITHOUT_CTX", "text": token.norm})
                return

            name = normalize_athlete_name(token.norm)
            if not self._looks_like_person_name(name):
                self.trace.emit({
                    "action": "REJECT_RELAY_MEMBER",
                    "text": name,
                    "reason": "not_person_like",
                    "club": self.ctx.relay_ctx.club_name if self.ctx.relay_ctx else None,
                })
                # Si estamos en un relevo incompleto y aparece algo raro, cerramos el relevo para no “chupar” cabeceras
                if self.ctx.relay_ctx:
                    self._flush_relay_context(competition_id, season_id, date, reason="incomplete_relay_boundary")
                    self.ctx.state = State.IN_RESULTS
                return

            self.ctx.relay_ctx.members.append(name)

            if len(self.ctx.relay_ctx.members) >= self.ctx.relay_ctx.expected_size:
                self._flush_relay_context(competition_id, season_id, date, reason="expected_size")
                self.ctx.state = State.IN_RESULTS
                return
            
        if token.type == TokenType.INDIVIDUAL_ROW and self.ctx.current_event_relay:
            # En relays la primera fila trae nombre+año+club => es TEAM_ROW real
            if self.ctx.relay_ctx:
                self._flush_relay_context(competition_id, season_id, date, reason="new_team_row")
            self._open_relay_from_team_row(token.norm)
            return

        if token.type == TokenType.INDIVIDUAL_ROW:
            if self.ctx.state != State.IN_RESULTS:
                # ignorar "falsos rows" en cabeceras (fechas, etc.)
                return
            self._handle_individual_row(token.norm, competition_id, season_id, date)
            return
        
        # NOISE: ignore

    def finalize(self, *, competition_id: Optional[str] = None, season_id: Optional[str] = None, date: Optional[str] = None) -> None:
        if self.ctx.relay_ctx and competition_id and season_id and date:
            self._flush_relay_context(competition_id, season_id, date, reason="finalize")
            self.ctx.state = State.IN_RESULTS
