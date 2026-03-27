from __future__ import annotations

import json
from typing import Protocol, Dict, Any, Optional


class TraceSink(Protocol):
    def emit(self, record: Dict[str, Any]) -> None:
        ...


class NullTrace:
    def emit(self, record):
        return
    def close(self):
        return


class JsonlTrace:
    def __init__(self, path: str) -> None:
        self.path = path
        self._fh = open(path, "w", encoding="utf-8")

    def emit(self, record: Dict[str, Any]) -> None:
        self._fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def close(self) -> None:
        try:
            self._fh.close()
        except Exception:
            pass


class StdoutTrace:
    def emit(self, record: Dict[str, Any]) -> None:
        print(json.dumps(record, ensure_ascii=False))