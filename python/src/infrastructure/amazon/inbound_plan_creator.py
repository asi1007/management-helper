from __future__ import annotations

import logging
import re
import time
from typing import Any

import httpx

from shared.config import DEFAULT_MARKETPLACE_ID, SHIP_FROM_ADDRESS

logger = logging.getLogger(__name__)

API_BASE_2024 = "https://sellingpartnerapi-fe.amazon.com/inbound/fba/2024-03-20"
API_BASE_V0 = "https://sellingpartnerapi-fe.amazon.com/fba/inbound/v0"
MAX_ITEM_PAGES = 50
POLL_INTERVAL_SEC = 5
POLL_TIMEOUT_SEC = 300
MAX_RETRIES = 3


class InboundPlanCreator:
    def __init__(self, auth_token: str) -> None:
        self._auth_token = auth_token
        self._headers = {
            "Accept": "application/json",
            "x-amz-access-token": auth_token,
            "Content-Type": "application/json",
        }

    def create_plan(self, items: dict[str, dict[str, Any]]) -> dict[str, Any]:
        result = self._create_inbound_plan_with_retry(items)
        inbound_plan_id = result.get("inboundPlanId", "")
        operation_id = result.get("operationId", "")
        if operation_id:
            self._wait_operation(operation_id)
        link = f"https://sellercentral.amazon.co.jp/fba/sendtoamazon/confirm_content_step?wf={inbound_plan_id}"
        return {"inboundPlanId": inbound_plan_id, "link": link}

    def _create_inbound_plan_with_retry(self, items: dict[str, dict[str, Any]]) -> dict[str, Any]:
        prep_overrides: dict[str, str] = {}
        for attempt in range(MAX_RETRIES):
            body = self._build_create_plan_body(items, prep_overrides)
            response = httpx.post(f"{API_BASE_2024}/inboundPlans", json=body, headers=self._headers, timeout=30.0)
            data = response.json()
            if response.status_code in (200, 202):
                logger.info("納品プラン作成成功: %s", data)
                return data
            errors = data.get("errors", [])
            new_overrides = self._parse_prep_owner_from_errors(errors, body["items"])
            if new_overrides and attempt < MAX_RETRIES - 1:
                prep_overrides.update(new_overrides)
                logger.warning("prepOwnerエラー -> 個別修正でリトライ (attempt=%d, fixes=%d)", attempt + 1, len(new_overrides))
                continue
            messages = "; ".join(f'{e.get("code")}: {e.get("message")}' for e in errors)
            raise RuntimeError(f"納品プラン作成エラー: {messages}")
        raise RuntimeError("納品プラン作成: リトライ上限到達")

    @staticmethod
    def _parse_prep_owner_from_errors(errors: list[dict[str, Any]], sent_items: list[dict[str, Any]]) -> dict[str, str]:
        sent_skus_by_internal_id: dict[str, str] = {}
        for item in sent_items:
            sent_skus_by_internal_id[item["msku"]] = item["msku"]

        overrides: dict[str, str] = {}
        for e in errors:
            msg = str(e.get("message", ""))
            match = re.search(r"ERROR: (\S+) (?:does not require|requires) prepOwner.*?Accepted values: \[([^\]]+)\]", msg)
            if not match:
                continue
            error_id = match.group(1)
            accepted_raw = match.group(2)
            accepted = [v.strip() for v in accepted_raw.split(",")]
            preferred = accepted[0]

            if error_id in sent_skus_by_internal_id:
                overrides[error_id] = preferred
            else:
                idx_match = re.search(r"items\.(\d+)\.", msg)
                if idx_match:
                    idx = int(idx_match.group(1)) - 1
                    if 0 <= idx < len(sent_items):
                        overrides[sent_items[idx]["msku"]] = preferred

        return overrides

    def _build_create_plan_body(self, items: dict[str, dict[str, Any]], prep_overrides: dict[str, str]) -> dict[str, Any]:
        item_list = []
        for sku, info in items.items():
            item_list.append({
                "msku": sku, "asin": info.get("asin", ""),
                "quantity": info.get("quantity", 0),
                "labelOwner": info.get("labelOwner", "SELLER"),
                "prepOwner": prep_overrides.get(sku, "SELLER"),
            })
        return {
            "destinationMarketplaces": [DEFAULT_MARKETPLACE_ID],
            "sourceAddress": SHIP_FROM_ADDRESS,
            "items": item_list,
        }

    def _wait_operation(self, operation_id: str) -> dict[str, Any]:
        url = f"{API_BASE_2024}/operations/{operation_id}"
        elapsed = 0
        while elapsed < POLL_TIMEOUT_SEC:
            response = httpx.get(url, headers=self._headers, timeout=30.0)
            data = response.json()
            status = data.get("operationStatus", "")
            if status == "SUCCESS":
                logger.info("オペレーション完了: %s", operation_id)
                return data
            if status == "FAILED":
                raise RuntimeError(f"オペレーション失敗: {data}")
            time.sleep(POLL_INTERVAL_SEC)
            elapsed += POLL_INTERVAL_SEC
        raise TimeoutError(f"オペレーションタイムアウト ({POLL_TIMEOUT_SEC}秒)")

    def get_placement_options(self, inbound_plan_id: str) -> dict[str, Any]:
        url = f"{API_BASE_2024}/inboundPlans/{inbound_plan_id}/placementOptions"
        response = httpx.post(url, json={}, headers=self._headers, timeout=30.0)
        data = response.json()
        operation_id = data.get("operationId", "")
        if operation_id:
            result = self._wait_operation(operation_id)
            return result.get("operationProblems", result)
        return data

    def confirm_placement_option(self, inbound_plan_id: str, placement_option_id: str) -> dict[str, Any]:
        url = f"{API_BASE_2024}/inboundPlans/{inbound_plan_id}/placementOptions/{placement_option_id}/confirmation"
        response = httpx.post(url, json={}, headers=self._headers, timeout=30.0)
        response.raise_for_status()
        return response.json()

    def list_shipments(self, inbound_plan_id: str) -> list[dict[str, Any]]:
        url = f"{API_BASE_2024}/inboundPlans/{inbound_plan_id}/shipments"
        response = httpx.get(url, headers=self._headers, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        return data.get("shipments", data.get("body", {}).get("shipments", []))

    def get_shipment_status(self, shipment_id: str) -> str:
        url = f"{API_BASE_V0}/shipments"
        params = {
            "MarketplaceId": DEFAULT_MARKETPLACE_ID,
            "ShipmentIdList": shipment_id,
            "QueryType": "SHIPMENT",
        }
        response = httpx.get(url, params=params, headers=self._headers, timeout=30.0)
        data = response.json()
        members = data.get("payload", {}).get("ShipmentData", [])
        if isinstance(members, list) and members:
            return members[0].get("ShipmentStatus", "")
        return ""

    def get_shipment_items(self, shipment_id: str) -> list[dict[str, Any]]:
        items_by_sku: dict[str, dict[str, Any]] = {}
        seen_tokens: set[str] = set()
        next_token: str | None = None
        for _ in range(MAX_ITEM_PAGES):
            page_items, next_token = self._fetch_items_page(shipment_id, next_token)
            added_new = False
            for item in page_items:
                sku = str(item.get("SellerSKU", item.get("msku", item.get("sellerSku", "")))).strip()
                if not sku or sku in items_by_sku:
                    continue
                items_by_sku[sku] = item
                added_new = True
            if not next_token or next_token in seen_tokens or not added_new:
                break
            seen_tokens.add(next_token)
        return list(items_by_sku.values())

    def _fetch_items_page(
        self, shipment_id: str, next_token: str | None
    ) -> tuple[list[dict[str, Any]], str | None]:
        url = f"{API_BASE_V0}/shipments/{shipment_id}/items"
        params: dict[str, Any] = {"MarketplaceId": DEFAULT_MARKETPLACE_ID}
        if next_token:
            params["NextToken"] = next_token
        response = httpx.get(url, params=params, headers=self._headers, timeout=30.0)
        data = response.json()
        payload = data.get("payload", {})
        return payload.get("ItemData", []), payload.get("NextToken")

    def get_plan_quantity_totals(self, inbound_plan_id: str) -> dict[str, Any]:
        shipments = self.list_shipments(inbound_plan_id)
        total_shipped = 0
        total_received = 0
        shipment_ids: list[str] = []
        for s in shipments:
            sid = s.get("shipmentId", "")
            if sid:
                shipment_ids.append(sid)
            items = self.get_shipment_items(sid)
            for item in items:
                total_shipped += int(item.get("QuantityShipped", item.get("quantityShipped", 0)))
                total_received += int(item.get("QuantityReceived", item.get("quantityReceived", 0)))
        return {"quantityShipped": total_shipped, "quantityReceived": total_received, "shipmentIds": shipment_ids}

    def get_packing_group_id(self, inbound_plan_id: str) -> str:
        ids = self._list_packing_group_ids(inbound_plan_id)
        if not ids:
            raise RuntimeError("packingGroupが見つかりません")
        return ids[0]

    def get_packing_groups(self, inbound_plan_id: str) -> list[dict[str, Any]]:
        ids = self._list_packing_group_ids(inbound_plan_id)
        groups: list[dict[str, Any]] = []
        for pg_id in ids:
            items = self.get_packing_group_items(inbound_plan_id, pg_id)
            groups.append({"packingGroupId": pg_id, "items": items})
        return groups

    def _list_packing_group_ids(self, inbound_plan_id: str) -> list[str]:
        url = f"{API_BASE_2024}/inboundPlans/{inbound_plan_id}/packingOptions"
        response = httpx.get(url, headers=self._headers, timeout=30.0)
        response.raise_for_status()
        options = response.json().get("packingOptions", [])
        if not options:
            return []
        return list(options[0].get("packingGroups", []))

    def get_packing_group_items(self, inbound_plan_id: str, packing_group_id: str) -> list[dict[str, Any]]:
        url = f"{API_BASE_2024}/inboundPlans/{inbound_plan_id}/packingGroups/{packing_group_id}/items"
        response = httpx.get(url, headers=self._headers, timeout=30.0)
        response.raise_for_status()
        return response.json().get("items", [])

    def get_shipment_labels(self, shipment_id: str, *, page_type: str = "A4_24", label_type: str = "SHIPMENT") -> bytes:
        url = f"{API_BASE_2024}/shipments/{shipment_id}/labels"
        params = {"pageType": page_type, "labelType": label_type}
        response = httpx.get(url, params=params, headers=self._headers, timeout=60.0)
        if response.status_code in (200, 202):
            data = response.json()
            download_url = data.get("downloadUrl", "")
            if download_url:
                pdf_response = httpx.get(download_url, timeout=60.0)
                pdf_response.raise_for_status()
                logger.info("ラベルPDFダウンロード完了: shipment_id=%s, size=%d", shipment_id, len(pdf_response.content))
                return pdf_response.content
        response.raise_for_status()
        raise RuntimeError(f"ラベルダウンロード失敗: {response.text}")

    def set_packing_information(self, inbound_plan_id: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{API_BASE_2024}/inboundPlans/{inbound_plan_id}/packingInformation"
        response = httpx.post(url, json=body, headers=self._headers, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        operation_id = data.get("operationId", "")
        if operation_id:
            return self._wait_operation(operation_id)
        return data
