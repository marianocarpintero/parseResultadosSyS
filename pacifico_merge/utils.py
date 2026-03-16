from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def index_by_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item['id']: item for item in items if isinstance(item, dict) and 'id' in item}


def ensure_list(obj: Any) -> list:
    return obj if isinstance(obj, list) else []


def ensure_dict(obj: Any) -> dict:
    return obj if isinstance(obj, dict) else {}
