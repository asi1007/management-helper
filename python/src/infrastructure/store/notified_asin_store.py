from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)


class NotifiedAsinStore:
    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)

    def exists(self) -> bool:
        return self._path.exists()

    def load(self) -> set[str]:
        if not self._path.exists():
            return set()
        try:
            stored = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("通知済みASINを読めませんでした（空として扱います）: %s", e)
            return set()
        return {str(asin).strip() for asin in stored.get("asins", []) if str(asin).strip()}

    def add(self, asins: Iterable[str]) -> None:
        merged = self.load() | {str(asin).strip() for asin in asins if str(asin).strip()}
        payload = {"asins": sorted(merged), "updated_at": date.today().isoformat()}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
