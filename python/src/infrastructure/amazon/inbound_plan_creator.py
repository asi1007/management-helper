from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from shared.config import DEFAULT_MARKETPLACE_ID, SHIP_FROM_ADDRESS

logger = logging.getLogger(__name__)

API_BASE_2024 = "https://sellingpartnerapi-fe.amazon.com/inbound/fba/2024-03-20"
API_BASE_V0 = "https://sellingpartnerapi-fe.amazon.com/fba/inbound/v0"
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
        prep_owners_to_try = ["SELLER", "NONE", "AMAZON"]
        for attempt, prep_owner in enumerate(prep_owners_to_try):
            body = self._build_create_plan_body(items, prep_owner)
            response = httpx.post(f"{API_BASE_2024}/inboundPlans", json=body, headers=self._headers, timeout=30.0)
            data = response.json()
            if response.status_code == 200:
                logger.info("納品プラン作成成功: %s", data)
                return data
            errors = data.get("errors", [])
            if self._is_prep_owner_error(errors) and attempt < len(prep_owners_to_try) - 1:
                logger.warning("prepOwnerエラー(%s) -> %sでリトライ", prep_owner, prep_owners_to_try[attempt + 1])
                continue
            messages = "; ".join(f'{e.get("code")}: {e.get("message")}' for e in errors)
            raise RuntimeError(f"納品プラン作成エラー: {messages}")
        raise RuntimeError("納品プラン作成: リトライ上限到達")

    def _build_create_plan_body(self, items: dict[str, dict[str, Any]], prep_owner: str) -> dict[str, Any]:
        item_list = []
        for sku, info in items.items():
            item_list.append({
                "msku": sku, "asin": info.get("asin", ""),
                "quantity": info.get("quantity", 0),
                "labelOwner": info.get("labelOwner", "SELLER"),
                "prepOwner": prep_owner,
            })
        return {
            "destinationMarketplaces": [DEFAULT_MARKETPLACE_ID],
            "sourceAddress": SHIP_FROM_ADDRESS,
            "items": item_list,
        }

    def _is_prep_owner_error(self, errors: list[dict[str, Any]]) -> bool:
        return any("prepowner" in str(e.get("message", "")).lower() for e in errors)

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
        url = f"{API_BASE_V0}/shipments/{shipment_id}"
        params = {"MarketplaceId": DEFAULT_MARKETPLACE_ID}
        response = httpx.get(url, params=params, headers=self._headers, timeout=30.0)
        data = response.json()
        payload = data.get("payload", {})
        members = payload.get("ShipmentData", payload.get("MemberList", []))
        if isinstance(members, list) and members:
            return members[0].get("ShipmentStatus", "")
        return ""

    def get_shipment_items(self, shipment_id: str) -> list[dict[str, Any]]:
        try:
            url = f"{API_BASE_2024}/shipments/{shipment_id}/items"
            response = httpx.get(url, headers=self._headers, timeout=30.0)
            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])
                if items:
                    return items
        except Exception:
            pass
        url = f"{API_BASE_V0}/shipments/{shipment_id}/items"
        params = {"MarketplaceId": DEFAULT_MARKETPLACE_ID}
        response = httpx.get(url, params=params, headers=self._headers, timeout=30.0)
        data = response.json()
        payload = data.get("payload", {})
        return payload.get("ItemData", [])

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
        url = f"{API_BASE_2024}/inboundPlans/{inbound_plan_id}/packingGroups"
        response = httpx.get(url, headers=self._headers, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        groups = data.get("packingGroups", [])
        if not groups:
            raise RuntimeError("packingGroupが見つかりません")
        return groups[0].get("packingGroupId", groups[0]) if isinstance(groups[0], dict) else groups[0]

    def get_packing_group_items(self, inbound_plan_id: str, packing_group_id: str) -> list[dict[str, Any]]:
        url = f"{API_BASE_2024}/inboundPlans/{inbound_plan_id}/packingGroups/{packing_group_id}/items"
        response = httpx.get(url, headers=self._headers, timeout=30.0)
        response.raise_for_status()
        return response.json().get("items", [])

    def set_packing_information(self, inbound_plan_id: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{API_BASE_2024}/inboundPlans/{inbound_plan_id}/packingInformation"
        response = httpx.post(url, json=body, headers=self._headers, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        operation_id = data.get("operationId", "")
        if operation_id:
            return self._wait_operation(operation_id)
        return data
