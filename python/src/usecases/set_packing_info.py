from __future__ import annotations

import logging
import re
from typing import Any

import click

from shared.config import AppConfig
from infrastructure.amazon.auth import get_auth_token
from infrastructure.amazon.inbound_plan_creator import InboundPlanCreator
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet

logger = logging.getLogger(__name__)


def set_packing_info(config: AppConfig, repo: BaseSheetsRepository, row_numbers: list[int]) -> None:
    access_token = get_auth_token(config.api_key, config.api_secret, config.refresh_token)
    sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    sheet.get_rows_by_numbers(row_numbers)
    plan_cell = str(sheet.data[0].get("納品プラン") or "").strip() if sheet.data else ""
    inbound_plan_id = extract_inbound_plan_id(plan_cell)
    if not inbound_plan_id:
        raise RuntimeError("納品プランIDが取得できません")
    click.echo(f"納品プランID: {inbound_plan_id}")
    click.echo("箱情報を入力してください（例: 1-2：60*40*32 29.1KG）")
    click.echo("空行で入力終了:")
    lines: list[str] = []
    while True:
        line = input()
        if not line.strip():
            break
        lines.append(line)
    carton_text = "\n".join(lines)
    cartons = parse_carton_input(carton_text)
    if not cartons:
        raise RuntimeError("箱情報がパースできません")
    creator = InboundPlanCreator(access_token)
    packing_group_id = creator.get_packing_group_id(inbound_plan_id)
    items = creator.get_packing_group_items(inbound_plan_id, packing_group_id)
    body = build_packing_body(packing_group_id, cartons, items)
    creator.set_packing_information(inbound_plan_id, body)
    click.echo("梱包情報の送信が完了しました")


PLAN_ID_PATTERN = r"wf[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}|wf[a-zA-Z0-9]+"
LABELING_PREP_TYPE = "ITEM_LABELING"


def extract_inbound_plan_id(cell_value: str) -> str:
    match = re.search(rf"wf=({PLAN_ID_PATTERN})", cell_value)
    if match:
        return match.group(1)
    match = re.search(rf"({PLAN_ID_PATTERN})", cell_value)
    return match.group(1) if match else ""


def parse_carton_input(text: str) -> list[dict[str, Any]]:
    cartons: list[dict[str, Any]] = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        match = re.match(
            r"(\d+(?:-\d+)?)\s*[：:]\s*(\d+(?:\.\d+)?)\s*[*×x]\s*(\d+(?:\.\d+)?)\s*[*×x]\s*(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s*[Kk][Gg]",
            line,
        )
        if not match:
            logger.warning("パース失敗: %s", line)
            continue
        box_range = match.group(1)
        length_cm = float(match.group(2))
        width_cm = float(match.group(3))
        height_cm = float(match.group(4))
        weight_kg = float(match.group(5))
        if "-" in box_range:
            start, end = box_range.split("-")
            count = int(end) - int(start) + 1
        else:
            count = 1
        cartons.append({
            "count": count,
            "length": length_cm,
            "width": width_cm,
            "height": height_cm,
            "weight": weight_kg,
        })
    return cartons


def build_packing_body(
    packing_group_id: str, cartons: list[dict[str, Any]], items: list[dict[str, Any]],
) -> dict[str, Any]:
    box_items = [
        {
            "msku": item.get("msku", ""),
            "quantity": item.get("quantity", 0),
            "labelOwner": item.get("labelOwner", "SELLER"),
            "prepOwner": _prep_owner_of(item),
        }
        for item in items
    ]
    package_groups = [
        {
            "packingGroupId": packing_group_id,
            "boxes": [{
                "contentInformationSource": "BOX_CONTENT_PROVIDED",
                "weight": {"unit": "KG", "value": carton["weight"]},
                "dimensions": {
                    "unitOfMeasurement": "CM",
                    "length": carton["length"],
                    "width": carton["width"],
                    "height": carton["height"],
                },
                "quantity": carton["count"],
                "items": box_items,
            }],
        }
        for carton in cartons
    ]
    return {"packageGroupings": package_groups}


def _prep_owner_of(item: dict[str, Any]) -> str:
    for instruction in item.get("prepInstructions") or []:
        if instruction.get("prepType") == LABELING_PREP_TYPE:
            continue
        if instruction.get("prepOwner"):
            return str(instruction["prepOwner"])
    return "NONE"
