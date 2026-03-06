from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass(frozen=True)
class Season:
    id: str
    label: str


@dataclass(frozen=True)
class Competition:
    id: str
    season_id: str
    name: str
    name_clean: Optional[str] = None
    date: Optional[str] = None
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    location: str = ""
    region: str = ""
    pool_type: str = ""
    source_file: str = ""


@dataclass(frozen=True)
class Club:
    id: str
    name: str
    slug: str


@dataclass(frozen=True)
class Athlete:
    id: str
    name: str
    birth_year: Optional[int] = None


@dataclass(frozen=True)
class Event:
    id: str
    base: str
    discipline: str
    category: str
    sex: str
    relay: bool
    distance_m: Optional[float] = None


@dataclass(frozen=True)
class TimeInfo:
    display: Optional[str]
    seconds: Optional[float]
    raw: Optional[str]


@dataclass(frozen=True)
class Labels:
    x: str


@dataclass(frozen=True)
class Result:
    id: str
    date: str
    season_id: str
    competition_id: str
    event_id: str
    athlete_id: str
    club_id: str
    time: TimeInfo
    status: str
    position: Optional[int] = None
    points: Optional[int] = None
    series_type: str = "Final"
    labels: Labels = field(default_factory=lambda: Labels(x=""))
    heat: Optional[int] = None


@dataclass
class OutputDocument:
    meta: Dict[str, Any]
    dimensions: Dict[str, Any]
    results: List[Dict[str, Any]]
    tree: Optional[List[Dict[str, Any]]] = None