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
from dataclasses import asdict
from typing import Dict, List, Optional, Any
from .schema import Season, Competition, Club, Athlete, Event, Result
from .normalize import strip_accents, normalize_spaces
import re


def athlete_name_key(name: str) -> str:
    s = strip_accents(name or "").lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)   # quita puntuación (incluye coma rara)
    s = normalize_spaces(s)
    return s


class DimensionsBuilder:
    """
    Acumulador deduplicado de dimensiones.
    - No parsea PDFs.
    - No decide reglas de negocio.
    - Solo almacena y devuelve estructuras listas para JSON.
    """

    def __init__(self) -> None:
        self.seasons: Dict[str, Season] = {}
        self.competitions: Dict[str, Competition] = {}
        self.clubs: Dict[str, Club] = {}
        self.athletes: Dict[str, Athlete] = {}
        self.athlete_best_by_name: Dict[str, str] = {}  # name_key -> athlete_id
        self.events: Dict[str, Event] = {}

    def add_season(self, season: Season) -> None:
        self.seasons.setdefault(season.id, season)

    def add_competition(self, comp: Competition) -> None:
        self.competitions.setdefault(comp.id, comp)

    def add_club(self, club: Club) -> None:
        self.clubs.setdefault(club.id, club)

    def add_athlete(self, athlete: Athlete) -> None:
        key = athlete_name_key(athlete.name)
        incoming_has_year = athlete.birth_year is not None

        # Si no hay nombre key, fallback simple
        if not key:
            self.athletes.setdefault(athlete.id, athlete)
            return

        best_id = self.athlete_best_by_name.get(key)
        if best_id:
            best = self.athletes.get(best_id)
            best_has_year = best and best.birth_year is not None

            # Si ya tenemos con año, NO ignorar el "_na" todavía.
            # Lo guardamos temporalmente para poder remapear results, y luego se podará.
            if best_has_year and not incoming_has_year:
                self.athletes.setdefault(athlete.id, athlete)
                return

            # Si llega con año y el mejor era "_na", reemplazar
            if incoming_has_year and (not best_has_year):
                # quitar el anterior (na) y poner el nuevo como best
                self.athletes.pop(best_id, None)
                self.athletes[athlete.id] = athlete
                self.athlete_best_by_name[key] = athlete.id
                return

            # Si ambos tienen año, nos quedamos con el primero (o podrías decidir por otra regla)
            return

        # Primer atleta para ese nombre
        self.athletes[athlete.id] = athlete
        self.athlete_best_by_name[key] = athlete.id

    def add_event(self, event):
        self.events.setdefault(event.id, event)

    def build(self) -> Dict[str, Any]:
        """
        Devuelve un dict con listas de dicts (serializable a JSON) en el formato:
        {
          "seasons": [...],
          "competitions": [...],
          "clubs": [...],
          "athletes": [...],
          "events": [...]
        }
        """
        return {
            "seasons": [asdict(x) for x in self.seasons.values()],
            "competitions": [asdict(x) for x in self.competitions.values()],
            "clubs": [asdict(x) for x in self.clubs.values()],
            "athletes": [asdict(x) for x in self.athletes.values()],
            "events": [asdict(x) for x in self.events.values()],
        }


class ResultsBuilder:
    """
    Acumulador de results (lista). Mantiene orden de inserción.
    """

    def __init__(self) -> None:
        self._results: List[Result] = []

    def add(self, r: Result) -> None:
        self._results.append(r)

    def build(self) -> List[Dict[str, Any]]:
        return [asdict(r) for r in self._results]

    @property
    def results(self) -> List[Result]:
        return self._results


def tree_sex_code(sex: Optional[str]) -> Optional[str]:
    """
    Convierte sexo del evento a código para el tree: M/F/X.
    Acepta variantes ('m','f','x','mixto', etc.).
    """
    if not sex:
        return None
    s = str(sex).lower().strip()
    if s.startswith("m"):
        return "M"
    if s.startswith("f"):
        return "F"
    if s.startswith("x") or s.startswith("mixto"):
        return "X"
    return None


def build_tree(dimensions: Dict[str, Any], results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Construye el tree a partir de:
      - dimensions: dict con listas {seasons, competitions, events}
      - results: lista de results (schema Pacifico)

    Nota:
    - Un event "pertenece" a una competition SOLO a través de results.
    - Por eso, los events se cuelgan bajo cada competition según aparezcan en results.
    """

    # --------------------------------------------------
    # ---- índices base ----
    # --------------------------------------------------
    seasons_by_id = {s["id"]: s for s in dimensions.get("seasons", [])}
    competitions_by_id = {c["id"]: c for c in dimensions.get("competitions", [])}
    events_by_id = {e["id"]: e for e in dimensions.get("events", [])}
    athletes_by_id = {a["id"]: a for a in dimensions.get("athletes", [])}
    clubs_by_id = {c["id"]: c for c in dimensions.get("clubs", [])}

    # --------------------------------------------------
    # ---- estructura base del tree (por temporada) ----
    # --------------------------------------------------
    tree_by_season: Dict[str, Dict[str, Any]] = {}
    for season_id, season in seasons_by_id.items():
        tree_by_season[season_id] = {
            "season_id": season_id,
            "season_label": season.get("label"),
            "competitions": []
        }

    # --------------------------------------------------
    # ---- añadir competitions a seasons ----
    # --------------------------------------------------
    comp_nodes: Dict[str, Dict[str, Any]] = {}
    for comp_id, comp in competitions_by_id.items():
        season_id = comp.get("season_id")
        if season_id not in tree_by_season:
            # si falta season, no lo colgamos
            continue

        comp_node = {
            "competition_id": comp_id,
            "season_id": season_id,
            "date": comp.get("date"),
            "name": comp.get("name"),
            "name_clean": comp.get("name_clean", comp.get("name")),
            "location": comp.get("location"),
            "region": comp.get("region"),
            "pool_type": comp.get("pool_type"),
            "events": []
        }
        tree_by_season[season_id]["competitions"].append(comp_node)
        comp_nodes[comp_id] = comp_node

    # --------------------------------------------------------
    # ---- preparar nodos de events (únicos por event_id) ----
    # --------------------------------------------------------
    # Ojo: se reutiliza el mismo objeto event_node cuando cuelga en varias competitions.
    # Esto está bien si un event_id solo aparece en una competition (lo normal).
    event_nodes: Dict[str, Dict[str, Any]] = {}
    for event_id, event in events_by_id.items():
        event_nodes[event_id] = {
            "event_id": event_id,
            "base": event.get("base"),
            "sex": tree_sex_code(event.get("sex")),
            "category": event.get("category"),
            "athletes": []
        }

    # ----------------------------------------------------------------
    # ---- distribuir events dentro de competitions según results ----
    # ----------------------------------------------------------------
    for r in results:
        comp_id = r.get("competition_id")
        event_id = r.get("event_id")
        # nodos de evento por competición: (comp_id, event_id) -> node
        comp_event_nodes: Dict[tuple[str, str], Dict[str, Any]] = {}

        if comp_id not in comp_nodes:
            continue
        if event_id not in event_nodes:
            continue

        # --------------------------------------------------
        # colgar event en competition si no está
        # --------------------------------------------------
        comp_node = comp_nodes[comp_id]

        key = (comp_id, event_id)
        ev_node = comp_event_nodes.get(key)
        if ev_node is None:
            event = events_by_id.get(event_id, {})
            ev_node = {
                "event_id": event_id,
                "base": event.get("base"),
                "sex": tree_sex_code(event.get("sex")),
                "category": event.get("category"),
                "athletes": []
            }
            comp_event_nodes[key] = ev_node
            comp_node["events"].append(ev_node)

        # --------------------------------------------------
        # ---- construir nodo de atleta en el tree ----
        # --------------------------------------------------
# TODO #15 No siempre salen los atletas del equipo en json aunque estén en pdf
        time_obj = r.get("time") or {}
        athlete_id = r.get("athlete_id")
        ath = athletes_by_id.get(athlete_id, {})
        club_id = r.get("club_id")
        club = clubs_by_id.get(club_id, {})

        athlete_node = {
            "athlete_id": athlete_id,
#            "name": ath.get("name") or athlete_id,
            "club_id": club_id,
#            "club_name": club.get("name"),
            "status": r.get("status"),
            "position": r.get("position"),
        }
        # heat opcional
        if "heat" in r and r.get("heat") is not None:
            athlete_node["heat"] = r.get("heat")
        # resto de campos
        athlete_node.update({
            "series_type": r.get("series_type"),
            "time": {
                "display": time_obj.get("display"),
                "seconds": time_obj.get("seconds"),
                "raw": time_obj.get("raw"),
            },
            "converted_time": time_obj.get("display"),
        })

        ev_node["athletes"].append(athlete_node)

    return list(tree_by_season.values())


# ------------------------------------------------------------
# Toma solo el club filtrado y las dimensiones relacionadas (competición/evento/temporada) para evitar ruido en el árbol final.
# ------------------------------------------------------------
def prune_dimensions_by_results(dims_dict: Dict[str, Any], results_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    comp_ids = {r["competition_id"] for r in results_list if r.get("competition_id")}
    event_ids = {r["event_id"] for r in results_list if r.get("event_id")}
    club_ids = {r["club_id"] for r in results_list if r.get("club_id")}
    athlete_ids = {r["athlete_id"] for r in results_list if r.get("athlete_id")}

    dims_dict["competitions"] = [c for c in dims_dict.get("competitions", []) if c.get("id") in comp_ids]
    dims_dict["events"] = [e for e in dims_dict.get("events", []) if e.get("id") in event_ids]
    dims_dict["clubs"] = [c for c in dims_dict.get("clubs", []) if c.get("id") in club_ids]
    dims_dict["athletes"] = [a for a in dims_dict.get("athletes", []) if a.get("id") in athlete_ids]

    season_ids = {c.get("season_id") for c in dims_dict.get("competitions", []) if c.get("season_id")}
    dims_dict["seasons"] = [s for s in dims_dict.get("seasons", []) if s.get("id") in season_ids]

    return dims_dict


def reconcile_athletes_and_results(dims_dict: Dict[str, Any], results_list: List[Dict[str, Any]]) -> None:
    # indices
    athletes = dims_dict.get("athletes", [])
    id_to_name = {a["id"]: a.get("name", "") for a in athletes}
    id_to_year = {a["id"]: a.get("birth_year") for a in athletes}

    # name_key -> best athlete_id (preferimos con año)
    best_by_key: Dict[str, str] = {}
    for a in athletes:
        k = athlete_name_key(a.get("name", ""))
        if not k:
            continue
        aid = a["id"]
        has_year = a.get("birth_year") is not None
        if k not in best_by_key:
            best_by_key[k] = aid
        else:
            cur = best_by_key[k]
            cur_has_year = id_to_year.get(cur) is not None
            if has_year and not cur_has_year:
                best_by_key[k] = aid

    # Remap results athlete_id
    remap: Dict[str, str] = {}
    for r in results_list:
        aid = r.get("athlete_id")
        if not aid:
            continue
        name = id_to_name.get(aid, "")
        k = athlete_name_key(name)
        best = best_by_key.get(k)
        if best and best != aid:
            remap[aid] = best

    if remap:
        for r in results_list:
            aid = r.get("athlete_id")
            if aid in remap:
                r["athlete_id"] = remap[aid]

        # Podar athletes que ya no se usan
        used = {r["athlete_id"] for r in results_list if r.get("athlete_id")}
        dims_dict["athletes"] = [a for a in dims_dict.get("athletes", []) if a["id"] in used]

        