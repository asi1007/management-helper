from __future__ import annotations
from typing import Protocol
from domain.inspection.value_objects.inspection_master_catalog import InspectionMasterCatalog


class IInspectionMasterRepository(Protocol):
    def load(self) -> InspectionMasterCatalog: ...
