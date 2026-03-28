from __future__ import annotations

import logging
import urllib.parse

import httpx

logger = logging.getLogger(__name__)

SELLER_ID = "APS8L6SC4MEPF"
MARKETPLACE_ID = "A1VC38T7YXB528"


class FnskuGetter:
    def __init__(self, auth_token: str) -> None:
        self._auth_token = auth_token
        self._headers = {
            "Accept": "application/json",
            "x-amz-access-token": auth_token,
        }

    def get_fnsku(self, msku: str) -> str:
        encoded_msku = urllib.parse.quote(msku.strip(), safe="")
        url = (
            f"https://sellingpartnerapi-fe.amazon.com/listings/2021-08-01"
            f"/items/{SELLER_ID}/{encoded_msku}"
            f"?marketplaceIds={MARKETPLACE_ID}"
        )
        response = httpx.get(url, headers=self._headers, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        summaries = data.get("summaries", [])
        if not summaries:
            raise RuntimeError(f"FNSKU が見つかりません: {msku}")
        fnsku = summaries[0].get("fnSku", "")
        if not fnsku:
            raise RuntimeError(f"FNSKU が空です: {msku}")
        logger.info("FNSKU取得: %s -> %s", msku, fnsku)
        return fnsku
