# Diagrama de esctructura (Mermaid)


flowchart TD
    ROOT[Root JSON]

    ROOT --> SEASONS["seasons[]"]
    ROOT --> COMPETITIONS["competitions[]"]

    SEASONS --> SEASON_ID["season_id"]
    SEASONS --> SEASON_LABEL["season_label"]

    COMPETITIONS --> COMP_ID["competition_id"]
    COMPETITIONS --> COMP_DATE["date"]
    COMPETITIONS --> COMP_NAME["name"]
    COMPETITIONS --> COMP_LOCATION["location"]
    COMPETITIONS --> POOL_TYPE["pool_type"]
    COMPETITIONS --> EVENTS["events[]"]

    EVENTS --> EVENT_ID["event_id"]
    EVENTS --> EVENT_BASE["base"]
    EVENTS --> EVENT_SEX["sex"]
    EVENTS --> EVENT_CATEGORY["category"]
    EVENTS --> ATHLETES["athletes[]"]

    ATHLETES --> ATHLETE_ID["athlete_id"]
    ATHLETES --> CLUB_ID["club_id"]
    ATHLETES --> STATUS["status"]
    ATHLETES --> POSITION["position"]
    ATHLETES --> SERIES_TYPE["series_type"]
    ATHLETES --> TIME["time"]
    ATHLETES --> CONVERTED_TIME["converted_time"]

    TIME --> DISPLAY["display"]
    TIME --> SECONDS["seconds"]
    TIME --> RAW["raw"]


# JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["competitions"],
  "properties": {
    "competitions": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["competition_id", "season_id", "date", "events"],
        "properties": {
          "competition_id": { "type": "string" },
          "season_id": { "type": "string" },
          "date": { "type": "string", "format": "date" },
          "name": { "type": "string" },
          "name_clean": { "type": "string" },
          "location": { "type": "string" },
          "region": { "type": "string" },
          "pool_type": { "type": "string" },
          "events": {
            "type": "array",
            "items": {
              "type": "object",
              "required": ["event_id", "base", "sex", "category", "athletes"],
              "properties": {
                "event_id": { "type": "string" },
                "base": { "type": "string" },
                "sex": { "enum": ["M", "F", "X"] },
                "category": { "type": "string" },
                "athletes": {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "required": ["athlete_id", "club_id", "status"],
                    "properties": {
                      "athlete_id": { "type": "string" },
                      "club_id": { "type": "string" },
                      "status": {
                        "enum": ["OK", "DSQ", "DNS", "BAJA"]
                      },
                      "position": { "type": ["integer", "null"] },
                      "series_type": { "type": "string" },
                      "time": {
                        "type": ["object", "null"],
                        "properties": {
                          "display": { "type": ["string", "null"] },
                          "seconds": { "type": ["number", "null"] },
                          "raw": { "type": ["string", "null"] }
                        }
                      },
                      "converted_time": { "type": ["string", "null"] }
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
```
