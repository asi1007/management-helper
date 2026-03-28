from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from domain.inspection.entities.inspection_master_item import InspectionMasterItem


class InspectionMasterCatalog:
    def __init__(self, items_by_asin: dict[str, InspectionMasterItem]) -> None:
        self._items_by_asin = dict(items_by_asin)

    def filter_by_asins(self, asins: list[str]) -> InspectionMasterCatalog:
        asin_set = set(asins)
        filtered = {k: v for k, v in self._items_by_asin.items() if k in asin_set}
        return InspectionMasterCatalog(items_by_asin=filtered)

    def has(self, asin: str) -> bool:
        return asin in self._items_by_asin

    def get(self, asin: str) -> InspectionMasterItem | None:
        return self._items_by_asin.get(asin)

    def size(self) -> int:
        return len(self._items_by_asin)

    def asins(self) -> list[str]:
        return list(self._items_by_asin.keys())
