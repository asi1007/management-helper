from __future__ import annotations

from enum import Enum
from typing import Any, Mapping

# 「状態」列は他列から導出される数式なので判定に使わない。
# 使うと「状態が決まらないから処理されない → 列が埋まらないから状態が決まらない」で循環する。
ARRIVED_ON = "到着日"
SHIPPED_ON = "発送日"
RECEIVED_ON = "受領日"
STOCK_COUNT = "在庫数"


class DeliveryStage(Enum):
    AWAITING_SUPPLIER = "イーウー到着待ち"
    AWAITING_SHIPMENT = "発送指示待ち"
    AWAITING_AMAZON = "Amazon倉庫到着待ち"
    DONE = "受領済み"

    @property
    def label(self) -> str:
        return self.value


def _filled(row: Mapping[str, Any] | Any, column: str) -> bool:
    getter = row.get if hasattr(row, "get") else (lambda k, d=None: None)
    return bool(str(getter(column) or "").strip())


def classify_stage(row: Mapping[str, Any] | Any) -> DeliveryStage | None:
    """仕入から納品までのどの工程で止まっているかを返す。対象外なら None"""
    if not _filled(row, "ASIN"):
        return None
    # 受領日が無くても在庫数が入っていれば Amazon に入っている
    if _filled(row, RECEIVED_ON) or _filled(row, STOCK_COUNT):
        return DeliveryStage.DONE
    if not _filled(row, ARRIVED_ON):
        return DeliveryStage.AWAITING_SUPPLIER
    if not _filled(row, SHIPPED_ON):
        return DeliveryStage.AWAITING_SHIPMENT
    return DeliveryStage.AWAITING_AMAZON
