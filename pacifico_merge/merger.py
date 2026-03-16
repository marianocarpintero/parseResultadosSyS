from __future__ import annotations

from pathlib import Path
from typing import Any, Tuple

from .utils import load_json, save_json, index_by_id, ensure_dict, ensure_list


DIM_KEYS = ('seasons', 'clubs', 'athletes', 'competitions', 'events')


def _merge_dimension_list(base: dict[str, Any], new: dict[str, Any], key: str) -> dict[str, int]:
    base_dims = ensure_dict(base.get('dimensions'))
    new_dims = ensure_dict(new.get('dimensions'))

    base_list = ensure_list(base_dims.get(key))
    new_list = ensure_list(new_dims.get(key))

    base_index = index_by_id(base_list)
    added = 0

    for item in new_list:
        if not isinstance(item, dict) or 'id' not in item:
            continue
        if item['id'] not in base_index:
            base_list.append(item)
            base_index[item['id']] = item
            added += 1

    base_dims[key] = base_list
    base['dimensions'] = base_dims

    return {'added': added, 'total': len(base_list)}


def _merge_results(base: dict[str, Any], new: dict[str, Any]) -> dict[str, int]:
    base_results = ensure_list(base.get('results'))
    new_results = ensure_list(new.get('results'))

    base_index = index_by_id(base_results)
    added = 0

    for r in new_results:
        if not isinstance(r, dict) or 'id' not in r:
            continue
        if r['id'] not in base_index:
            base_results.append(r)
            base_index[r['id']] = r
            added += 1

    base['results'] = base_results
    return {'added': added, 'total': len(base_results)}


def _find_or_create(d: dict[str, Any], key: str, default):
    if key not in d or d[key] is None:
        d[key] = default
    return d[key]


def _athlete_tree_key(a: dict[str, Any]) -> str | None:
    """Clave de deduplicación dentro de tree.event.athletes.

    Requisito (contrato actual): `series_type` y `heat` deben existir siempre.
    La clave es compuesta para evitar colisiones entre series/mangas:
      athlete_id + series_type + heat

    - `series_type`: string (recomendado no vacío)
    - `heat`: puede ser None, pero la clave debe existir
    """
    athlete_id = a.get('athlete_id')
    if not athlete_id:
        return None

    if 'series_type' not in a or 'heat' not in a:
        # Se considera inválido; la validación lo reportará.
        return None

    series_type = a.get('series_type') or ''
    heat = a.get('heat')
    heat_s = '' if heat is None else str(heat)
    return f'{athlete_id}|{series_type}|{heat_s}'


def _tree_index(pacifico_tree: list[dict[str, Any]]):
    season_idx: dict[str, dict[str, Any]] = {}
    comp_idx: dict[tuple[str, str], dict[str, Any]] = {}
    event_idx: dict[tuple[str, str, str], dict[str, Any]] = {}
    athlete_idx: set[tuple[str, str, str, str]] = set()

    for s in pacifico_tree:
        if not isinstance(s, dict):
            continue
        sid = s.get('season_id')
        if not sid:
            continue
        season_idx[sid] = s
        comps = ensure_list(_find_or_create(s, 'competitions', []))
        for c in comps:
            if not isinstance(c, dict):
                continue
            cid = c.get('competition_id')
            if not cid:
                continue
            comp_idx[(sid, cid)] = c
            evs = ensure_list(_find_or_create(c, 'events', []))
            for e in evs:
                if not isinstance(e, dict):
                    continue
                eid = e.get('event_id')
                if not eid:
                    continue
                event_idx[(sid, cid, eid)] = e
                athletes = ensure_list(_find_or_create(e, 'athletes', []))
                for a in athletes:
                    if not isinstance(a, dict):
                        continue
                    ak = _athlete_tree_key(a)
                    if ak:
                        athlete_idx.add((sid, cid, eid, ak))

    return season_idx, comp_idx, event_idx, athlete_idx


def _merge_tree(base: dict[str, Any], new: dict[str, Any]) -> dict[str, int]:
    base_tree = ensure_list(_find_or_create(base, 'tree', []))
    new_tree = ensure_list(new.get('tree'))

    season_idx, comp_idx, event_idx, athlete_idx = _tree_index(base_tree)

    added_seasons = added_comps = added_events = added_athletes = 0

    for out_season in new_tree:
        if not isinstance(out_season, dict):
            continue
        sid = out_season.get('season_id')
        if not sid:
            continue

        pac_season = season_idx.get(sid)
        if pac_season is None:
            base_tree.append(out_season)
            season_idx[sid] = out_season
            added_seasons += 1
            pac_season = out_season

        pac_comps = ensure_list(_find_or_create(pac_season, 'competitions', []))

        for out_comp in ensure_list(out_season.get('competitions')):
            if not isinstance(out_comp, dict):
                continue
            cid = out_comp.get('competition_id')
            if not cid:
                continue

            pac_comp = comp_idx.get((sid, cid))
            if pac_comp is None:
                pac_comps.append(out_comp)
                comp_idx[(sid, cid)] = out_comp
                added_comps += 1
                pac_comp = out_comp

            pac_events = ensure_list(_find_or_create(pac_comp, 'events', []))

            for out_event in ensure_list(out_comp.get('events')):
                if not isinstance(out_event, dict):
                    continue
                eid = out_event.get('event_id')
                if not eid:
                    continue

                pac_event = event_idx.get((sid, cid, eid))
                if pac_event is None:
                    pac_events.append(out_event)
                    event_idx[(sid, cid, eid)] = out_event
                    added_events += 1
                    pac_event = out_event

                pac_athletes = ensure_list(_find_or_create(pac_event, 'athletes', []))

                for out_ath in ensure_list(out_event.get('athletes')):
                    if not isinstance(out_ath, dict):
                        continue
                    ak = _athlete_tree_key(out_ath)
                    if not ak:
                        # inválido: sin series_type/heat; se reportará en validación
                        continue
                    key = (sid, cid, eid, ak)
                    if key not in athlete_idx:
                        pac_athletes.append(out_ath)
                        athlete_idx.add(key)
                        added_athletes += 1

    base['tree'] = base_tree
    return {
        'added_seasons': added_seasons,
        'added_competitions': added_comps,
        'added_events': added_events,
        'added_tree_items': added_athletes,
        'total_seasons': len(base_tree),
    }


def merge_pacifico(
    base_path: Path,
    new_path: Path,
    out_path: Path,
    merge_tree: bool = True,
) -> Tuple[dict[str, Any], dict[str, Any]]:
    base = load_json(base_path)
    new = load_json(new_path)

    counts: dict[str, dict[str, int]] = {}

    for key in DIM_KEYS:
        counts[f'dimensions.{key}'] = _merge_dimension_list(base, new, key)

    counts['results'] = _merge_results(base, new)

    tree_counts = None
    if merge_tree:
        tree_counts = _merge_tree(base, new)

    save_json(out_path, base)

    report = {
        'paths': {'base': str(base_path), 'new': str(new_path), 'out': str(out_path)},
        'counts': counts,
        'tree': tree_counts,
    }
    return base, report
