from __future__ import annotations

from domain.inspection.entities.inspection_master_item import InspectionMasterItem
from domain.inspection.value_objects.inspection_master_catalog import InspectionMasterCatalog
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository


class InspectionMasterRepo:
    def __init__(self, repo: BaseSheetsRepository, spreadsheet_id: str, sheet_gid: str | None = None) -> None:
        self._repo = repo
        self._spreadsheet_id = spreadsheet_id
        self._sheet_gid = sheet_gid

    def load(self) -> InspectionMasterCatalog:
        spreadsheet = self._repo.open_spreadsheet(self._spreadsheet_id)
        if self._sheet_gid:
            sheet = None
            for ws in spreadsheet.worksheets():
                if str(ws.id) == str(self._sheet_gid):
                    sheet = ws
                    break
            if sheet is None:
                sheet = spreadsheet.sheet1
        else:
            sheet = spreadsheet.sheet1
        all_values = sheet.get_all_values()
        if not all_values:
            return InspectionMasterCatalog(items_by_asin={})
        headers = [str(h).strip() for h in all_values[0]]
        asin_col = 0
        name_col = headers.index("商品名") if "商品名" in headers else 1
        point_col = headers.index("検品箇所") if "検品箇所" in headers else 2
        url_col = headers.index("詳細指示書URL") if "詳細指示書URL" in headers else 3
        items: dict[str, InspectionMasterItem] = {}
        for row_values in all_values[1:]:
            asin = str(row_values[asin_col]).strip() if len(row_values) > asin_col else ""
            if not asin:
                continue
            items[asin] = InspectionMasterItem(
                asin=asin,
                product_name=str(row_values[name_col]).strip() if len(row_values) > name_col else "",
                inspection_point=str(row_values[point_col]).strip() if len(row_values) > point_col else "",
                detail_instruction_url=str(row_values[url_col]).strip() if len(row_values) > url_col else "",
            )
        return InspectionMasterCatalog(items_by_asin=items)
