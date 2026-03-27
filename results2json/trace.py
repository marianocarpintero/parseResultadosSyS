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