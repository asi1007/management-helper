from __future__ import annotations

import re

PROVISIONAL_SKU_PATTERN = re.compile(r"^SKU-\d{10,}$")


def is_usable_sku(sku: str | None) -> bool:
    value = str(sku or "").strip()
    if not value:
        return False
    if value.startswith("#"):
        return False
    return not PROVISIONAL_SKU_PATTERN.match(value)
