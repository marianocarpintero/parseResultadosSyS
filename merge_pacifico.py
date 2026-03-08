import json
from pathlib import Path


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def index_by_id(items):
    return {item["id"]: item for item in items}


# ----------------------------
# Cargar ficheros
# ----------------------------
pacifico = load_json("./JSON/Pacifico.json")
out_all = load_json("./JSON/2025ddcc.json")

# ----------------------------
# MERGE: dimensions.seasons
# ----------------------------
pacifico_seasons = index_by_id(pacifico["dimensions"]["seasons"])
for season in out_all["dimensions"].get("seasons", []):
    if season["id"] not in pacifico_seasons:
        pacifico["dimensions"]["seasons"].append(season)

# ----------------------------
# MERGE: dimensions.athletes
# ----------------------------
pacifico_athletes = index_by_id(pacifico["dimensions"]["athletes"])
for athlete in out_all["dimensions"].get("athletes", []):
    if athlete["id"] not in pacifico_athletes:
        pacifico["dimensions"]["athletes"].append(athlete)

# ----------------------------
# MERGE: dimensions.competitions
# ----------------------------
pacifico_competitions = index_by_id(pacifico["dimensions"]["competitions"])
for competition in out_all["dimensions"].get("competitions", []):
    if competition["id"] not in pacifico_competitions:
        pacifico["dimensions"]["competitions"].append(competition)

# ----------------------------
# MERGE: dimensions.events
# ----------------------------
pacifico_events = index_by_id(pacifico["dimensions"]["events"])
for event in out_all["dimensions"].get("events", []):
    if event["id"] not in pacifico_events:
        pacifico["dimensions"]["events"].append(event)

# ----------------------------
# MERGE: results
# ----------------------------
pacifico_results = index_by_id(pacifico.get("results", []))
for result in out_all.get("results", []):
    if result["id"] not in pacifico_results:
        pacifico.setdefault("results", []).append(result)

# ----------------------------
# MERGE: tree (árbol con raíz en LISTA)
# ----------------------------
pacifico_tree = pacifico.setdefault("tree", [])
out_tree = out_all.get("tree", [])

def find_by_id(items, key, value):
    for item in items:
        if item.get(key) == value:
            return item
    return None


for out_season in out_tree:
    season_id = out_season.get("season_id")
    if not season_id:
        continue

    pac_season = find_by_id(pacifico_tree, "season_id", season_id)

    # 1️⃣ Season
    if pac_season is None:
        pacifico_tree.append(out_season)
        continue

    pac_competitions = pac_season.setdefault("competitions", [])

    for out_comp in out_season.get("competitions", []):
        comp_id = out_comp.get("competition_id")
        if not comp_id:
            continue

        pac_comp = find_by_id(pac_competitions, "competition_id", comp_id)

        # 2️⃣ Competition
        if pac_comp is None:
            pac_competitions.append(out_comp)
            continue

        pac_events = pac_comp.setdefault("events", [])

        for out_event in out_comp.get("events", []):
            event_id = out_event.get("event_id")
            if not event_id:
                continue

            pac_event = find_by_id(pac_events, "event_id", event_id)

            # 3️⃣ Event
            if pac_event is None:
                pac_events.append(out_event)
                continue

            pac_athletes = pac_event.setdefault("athletes", [])

            existing_athletes = {
                a.get("athlete_id") for a in pac_athletes
            }

            # 4️⃣ Athletes
            for out_athlete in out_event.get("athletes", []):
                athlete_id = out_athlete.get("athlete_id")
                if athlete_id not in existing_athletes:
                    pac_athletes.append(out_athlete)
                    existing_athletes.add(athlete_id)


# ----------------------------
# Guardar resultado
# ----------------------------
save_json("./JSON/Pacifico_merged.json", pacifico)

print("Merge completado → JSON/Pacifico_merged.json")