from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _resolve_sku_fnsku(
    cur_sku: str,
    cur_fnsku: str,
    pairs: list[tuple[str, str]],
    asin: str,
    asin_map: dict[str, tuple[str, str]],
) -> tuple[str | None, str | None]:
    if cur_sku and not cur_fnsku:
        for sku, fnsku in pairs:
            if sku == cur_sku:
                return None, (fnsku or None)
        return None, None
    if cur_fnsku and not cur_sku:
        for sku, fnsku in pairs:
            if fnsku == cur_fnsku:
                return (sku or None), None
        return None, None
    if not cur_sku and not cur_fnsku:
        if len(pairs) == 1:
            sku, fnsku = pairs[0]
            return (sku or None), (fnsku or None)
        candidate = asin_map.get(asin)
        if candidate and any(candidate[0] == sku for sku, _ in pairs):
            return candidate[0] or None, candidate[1] or None
        return None, None
    return None, None
