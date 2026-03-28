from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from infrastructure.amazon.fnsku_getter import FnskuGetter
from infrastructure.amazon.merchant_listings_sku_resolver import MerchantListingsSkuResolver
from infrastructure.spreadsheet.base_sheet import BaseSheet
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository

logger = logging.getLogger(__name__)

HEADER_ROW = 4


class PurchaseSheet(BaseSheet):
    def __init__(self, repo: BaseSheetsRepository, sheet_id: str, sheet_name: str) -> None:
        super().__init__(repo=repo, sheet_id=sheet_id, sheet_name=sheet_name, header_row=HEADER_ROW)

    def aggregate_items(self) -> dict[str, dict[str, Any]]:
        aggregated: dict[str, dict[str, Any]] = {}
        label_owner = "SELLER"
        for row in self.data:
            try:
                sku = str(row.get("SKU") or "").strip()
            except Exception:
                sku = ""
            try:
                asin = str(row.get("ASIN") or "").strip()
            except Exception:
                asin = ""
            try:
                quantity = int(row.get("購入数") or 0)
            except Exception:
                quantity = 0
            if not sku or quantity <= 0:
                logger.warning("納品プラン対象外: sku=%s, quantity=%d", sku, quantity)
                continue
            if sku not in aggregated:
                aggregated[sku] = {"msku": sku, "asin": asin, "quantity": 0, "labelOwner": label_owner}
            aggregated[sku]["quantity"] += quantity
        return aggregated

    def write_plan_result(self, plan_result: dict[str, Any]) -> None:
        plan_col = self._get_column_index_by_name("納品プラン") + 1
        ship_date_col = self._get_column_index_by_name("発送日") + 1
        link = str(plan_result.get("link", ""))
        inbound_plan_id = str(plan_result.get("inboundPlanId", ""))
        today = datetime.now().strftime("%Y/%m/%d")
        for row in self.data:
            row_num = row.row_number
            if link:
                display = inbound_plan_id or self._generate_plan_name_text()
                formula = f'=HYPERLINK("{link}", "{display}")'
                self.write_formula(row_num, plan_col, formula)
            elif inbound_plan_id:
                self.write_cell(row_num, plan_col, inbound_plan_id)
            self.write_cell(row_num, ship_date_col, today)

    def decrease_purchase_quantity(self, quantity: int) -> list[int]:
        qty_col = self._get_column_index_by_name("購入数") + 1
        zero_rows: list[int] = []
        for row in self.data:
            current = int(self._worksheet.cell(row.row_number, qty_col).value or 0)
            new_qty = max(0, current - quantity)
            self.write_cell(row.row_number, qty_col, new_qty)
            logger.info("行%d: 購入数を%dから%dに減らしました", row.row_number, current, new_qty)
            if new_qty == 0:
                zero_rows.append(row.row_number)
        return zero_rows

    def delete_rows(self, row_numbers: list[int]) -> None:
        for row_num in sorted(row_numbers, reverse=True):
            self._worksheet.delete_rows(row_num)
            logger.info("行%dを削除しました", row_num)

    def fetch_missing_fnskus(self, access_token: str) -> None:
        getter = FnskuGetter(access_token)
        fnsku_col_idx = self._get_column_index_by_name("FNSKU")
        fnsku_col = fnsku_col_idx + 1
        for row in self.data:
            fnsku = str(row.get("FNSKU") or "").strip()
            sku = str(row.get("SKU") or "").strip()
            if not fnsku and sku:
                fetched = getter.get_fnsku(sku)
                logger.info("FNSKU取得: %s -> %s", sku, fetched)
                self.write_cell(row.row_number, fnsku_col, fetched)
                row[fnsku_col_idx] = fetched

    def fill_missing_skus_from_asins(self, access_token: str) -> None:
        sku_col_idx = self._get_column_index_by_name("SKU")
        sku_col = sku_col_idx + 1
        asin_to_sku_local = self._build_asin_to_sku_local_map()
        targets = self._collect_missing_sku_targets()
        if not targets:
            logger.info("[SKU補完] SKU空白なし -> スキップ")
            return
        filled_local = 0
        still_missing_asins: list[str] = []
        for t in targets:
            resolved = asin_to_sku_local.get(t["asin"])
            if resolved:
                self.write_cell(t["row_num"], sku_col, resolved)
                t["row"][sku_col_idx] = resolved
                filled_local += 1
            else:
                still_missing_asins.append(t["asin"])
        unique_missing = list(set(still_missing_asins))
        if not unique_missing:
            logger.info("[SKU補完] ローカル流用で全件補完: %d/%d", filled_local, len(targets))
            return
        logger.info("[SKU補完] ローカル=%d/%d -> Reports API (ASIN数=%d)", filled_local, len(targets), len(unique_missing))
        resolver = MerchantListingsSkuResolver(access_token)
        asin_to_sku_remote = resolver.resolve_skus_by_asins(unique_missing)
        filled_remote = 0
        for t in targets:
            current = str(t["row"].get("SKU") or "").strip()
            if current:
                continue
            resolved = asin_to_sku_remote.get(t["asin"])
            if resolved:
                self.write_cell(t["row_num"], sku_col, resolved)
                t["row"][sku_col_idx] = resolved
                filled_remote += 1
        logger.info("[SKU補完] 完了: local=%d, remote=%d, total=%d/%d", filled_local, filled_remote, filled_local + filled_remote, len(targets))

    def write_plan_name_to_rows(self, instruction_url: str | None) -> int:
        date_str = self._format_date_mmdd()
        def value_func(row: Any, _index: int) -> Any:
            delivery_category = str(row.get("納品分類") or "").strip()
            plan_name = f"{date_str}{delivery_category}"
            if instruction_url:
                return {"type": "formula", "value": f'=HYPERLINK("{instruction_url}", "{plan_name}")'}
            return plan_name
        return self.write_column_by_func("プラン別名", value_func)

    def _build_asin_to_sku_local_map(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for row in self.all_data:
            sku = str(row.get("SKU") or "").strip()
            asin = str(row.get("ASIN") or "").strip()
            if asin and sku and asin not in result:
                result[asin] = sku
        return result

    def _collect_missing_sku_targets(self) -> list[dict[str, Any]]:
        targets: list[dict[str, Any]] = []
        for row in self.data:
            sku = str(row.get("SKU") or "").strip()
            asin = str(row.get("ASIN") or "").strip()
            if not sku:
                targets.append({"row": row, "row_num": row.row_number, "asin": asin})
        return targets

    def _generate_plan_name_text(self) -> str:
        date_str = self._format_date_mmdd()
        try:
            category = str(self.data[0].get("納品分類") or "").strip() if self.data else ""
        except Exception:
            category = ""
        return f"{date_str}{category}"

    def _format_date_mmdd(self) -> str:
        now = datetime.now()
        return f"{now.month:02d}/{now.day:02d}"
