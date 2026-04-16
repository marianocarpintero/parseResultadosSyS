#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
from pathlib import Path


def load_json(path):
    # Soporta UTF-8 con y sin BOM
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def build_record_id(competition_id, event_id, athlete_id):
    return f"cr_{competition_id}_{event_id}_{athlete_id}"


def extract_records(data):
    best_records = {}

    for season in data.get("tree", []):

        for competition in season.get("competitions", []):
            competition_id = competition["competition_id"]

            competition_block = {
                "id": competition_id,
                "season_id": competition.get("season_id"),
                "date": competition.get("date"),
                "name": competition.get("name"),
                "location": competition.get("location"),
                "pool_type": competition.get("pool_type"),
            }

            for event in competition.get("events", []):
                event_id = event["event_id"]
                category = event.get("category")
                sex = event.get("sex")

                for athlete in event.get("athletes", []):
                    time = athlete.get("time") or {}
                    seconds = time.get("seconds")

                    # ignorar sin tiempo válido
                    if seconds is None:
                        continue

                    key = (competition_id, event_id)

                    current = best_records.get(key)

                    if current is None or seconds < current["performance"]["time"]["seconds"]:
                        best_records[key] = {
                            "record_id": build_record_id(
                                competition_id,
                                event_id,
                                athlete["athlete_id"],
                            ),
                            "athlete": {
                                "id": athlete["athlete_id"],
                                "club_id": athlete.get("club_id"),
                            },
                            "competition": competition_block,
                            "performance": {
                                "event_id": event_id,
                                "base": event.get("base"),
                                "category": category,
                                "sex": sex,
                                "time": {
                                    "raw": time.get("raw"),
                                    "display": time.get("display"),
                                    "seconds": seconds,
                                },
                            },
                        }

    return list(best_records.values())


def main():
    if len(sys.argv) != 3:
        print("Uso: python records.py input.json output_records.json")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    data = load_json(input_path)
    records = extract_records(data)

    output = {
        "schema_version": "1.0",
        "records": records,
    }

    save_json(output, output_path)

    print(f"✔ Records generados: {len(records)}")


if __name__ == "__main__":
    main()