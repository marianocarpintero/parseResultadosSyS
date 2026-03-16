from __future__ import annotations

from typing import Any

from .utils import ensure_dict, ensure_list, index_by_id


REQUIRED_TOP_LEVEL = ('meta', 'dimensions', 'results')
REQUIRED_DIM_LISTS = ('seasons', 'clubs', 'athletes', 'competitions', 'events')


def validate_pacifico(data: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    stats: dict[str, Any] = {}

    for k in REQUIRED_TOP_LEVEL:
        if k not in data:
            errors.append(f"Falta clave top-level: '{k}'")

    dims = ensure_dict(data.get('dimensions'))

    for k in REQUIRED_DIM_LISTS:
        if k not in dims:
            warnings.append(f"Falta lista en dimensions: '{k}'")

    # IDs únicos en dimensions
    for k in REQUIRED_DIM_LISTS:
        lst = ensure_list(dims.get(k))
        seen = set()
        dups = 0
        for it in lst:
            if not isinstance(it, dict) or 'id' not in it:
                continue
            if it['id'] in seen:
                dups += 1
            seen.add(it['id'])
        if dups:
            errors.append(f"Duplicados en dimensions.{k}: {dups}")
        stats[f'dimensions.{k}.count'] = len(lst)

    # IDs únicos en results
    results = ensure_list(data.get('results'))
    seen_r = set()
    dup_r = 0
    for r in results:
        if not isinstance(r, dict) or 'id' not in r:
            continue
        if r['id'] in seen_r:
            dup_r += 1
        seen_r.add(r['id'])
    if dup_r:
        errors.append(f"Duplicados en results: {dup_r}")
    stats['results.count'] = len(results)

    # Referencias cruzadas (results → dimensions)
    seasons = set(index_by_id(ensure_list(dims.get('seasons'))).keys())
    clubs = set(index_by_id(ensure_list(dims.get('clubs'))).keys())
    athletes = set(index_by_id(ensure_list(dims.get('athletes'))).keys())
    comps = set(index_by_id(ensure_list(dims.get('competitions'))).keys())
    events = set(index_by_id(ensure_list(dims.get('events'))).keys())

    missing_refs = 0
    for r in results:
        if not isinstance(r, dict):
            continue
        sid = r.get('season_id')
        cid = r.get('competition_id')
        eid = r.get('event_id')
        aid = r.get('athlete_id')
        clid = r.get('club_id')

        if sid and sid not in seasons:
            errors.append(f"Result {r.get('id')} referencia season_id inexistente: {sid}")
            missing_refs += 1
        if cid and cid not in comps:
            errors.append(f"Result {r.get('id')} referencia competition_id inexistente: {cid}")
            missing_refs += 1
        if eid and eid not in events:
            errors.append(f"Result {r.get('id')} referencia event_id inexistente: {eid}")
            missing_refs += 1
        if aid and aid not in athletes:
            errors.append(f"Result {r.get('id')} referencia athlete_id inexistente: {aid}")
            missing_refs += 1
        if clid and clid not in clubs:
            errors.append(f"Result {r.get('id')} referencia club_id inexistente: {clid}")
            missing_refs += 1

    stats['results.missing_refs'] = missing_refs

    # Tree (warnings)
    tree = ensure_list(data.get('tree'))
    stats['tree.count'] = len(tree)
    if tree:
        _validate_tree(tree, seasons, comps, events, athletes, clubs, warnings, stats)

    return {'errors': errors, 'warnings': warnings, 'stats': stats}


def _validate_tree(tree, seasons, comps, events, athletes, clubs, warnings, stats):
    bad = 0
    for s in tree:
        if not isinstance(s, dict):
            continue
        sid = s.get('season_id')
        if sid and sid not in seasons:
            warnings.append(f"Tree season_id no existe en dimensions.seasons: {sid}")
            bad += 1

        for c in ensure_list(s.get('competitions')):
            if not isinstance(c, dict):
                continue
            cid = c.get('competition_id')
            if cid and cid not in comps:
                warnings.append(f"Tree competition_id no existe en dimensions.competitions: {cid}")
                bad += 1

            for e in ensure_list(c.get('events')):
                if not isinstance(e, dict):
                    continue
                eid = e.get('event_id')
                if eid and eid not in events:
                    warnings.append(f"Tree event_id no existe en dimensions.events: {eid}")
                    bad += 1

                for a in ensure_list(e.get('athletes')):
                    if not isinstance(a, dict):
                        continue
                    aid = a.get('athlete_id')
                    clid = a.get('club_id')

                    if aid and aid not in athletes:
                        warnings.append(f"Tree athlete_id no existe en dimensions.athletes: {aid}")
                        bad += 1
                    if clid and clid not in clubs:
                        warnings.append(f"Tree club_id no existe en dimensions.clubs: {clid}")
                        bad += 1

                    # Requisito: series_type y heat deben existir siempre (contrato actual)
                    if 'series_type' not in a:
                        warnings.append(f"Tree athlete sin series_type (obligatorio) en event_id={eid}, athlete_id={aid}")
                        bad += 1
                    if 'heat' not in a:
                        warnings.append(f"Tree athlete sin heat (obligatorio) en event_id={eid}, athlete_id={aid}")
                        bad += 1

    stats['tree.bad_refs'] = bad
