from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class InspectionMasterItem:
    asin: str
    product_name: str
    inspection_point: str
    detail_instruction_url: str
