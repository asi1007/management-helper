from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from pathlib import Path


class JsonFormatter(logging.Formatter):
    def __init__(self, version: str) -> None:
        super().__init__()
        self._version = version

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "version": self._version,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def get_version() -> str:
    toml_path = Path(__file__).resolve().parent.parent.parent / "pyproject.toml"
    try:
        import tomllib
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)
        return data["project"]["version"]
    except Exception:
        return "unknown"


def setup_logging() -> None:
    version = get_version()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(version))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
