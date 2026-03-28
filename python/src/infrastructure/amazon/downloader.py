from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SP_API_LABELS_URL = "https://sellingpartnerapi-fe.amazon.com/inbound/fba/2024-03-20/items/labels"
MAX_QUANTITY_PER_REQUEST = 999
LABEL_FOLDER_ID = "1ymbSzyiawRaREUwwaNYp4OzoGEOBgDNp"


class Downloader:
    def __init__(self, auth_token: str, drive_service: Any) -> None:
        self._auth_token = auth_token
        self._drive_service = drive_service
        self._headers = {
            "Accept": "application/json",
            "x-amz-access-token": auth_token,
            "Content-Type": "application/json",
        }

    def download_labels(self, sku_nums: list[dict[str, Any]], file_name: str) -> dict[str, Any]:
        chunks = self._split_by_quantity_limit(sku_nums)
        if len(chunks) == 1:
            return self._download_single_batch(chunks[0], file_name)
        return self._download_multiple_batches(chunks, file_name)

    def _download_single_batch(self, sku_nums: list[dict[str, Any]], file_name: str) -> dict[str, Any]:
        response_json = self._fetch_labels(sku_nums)
        pdf_bytes = self._download_pdf_bytes(response_json)
        url = self._save_to_drive(pdf_bytes, f"{file_name}.pdf")
        return {"url": url, "response_data": response_json}

    def _download_multiple_batches(self, chunks: list[list[dict[str, Any]]], file_name: str) -> dict[str, Any]:
        urls: list[str] = []
        last_response: dict[str, Any] = {}
        for i, chunk in enumerate(chunks):
            logger.info("ラベル分割ダウンロード: %d/%d", i + 1, len(chunks))
            response_json = self._fetch_labels(chunk)
            pdf_bytes = self._download_pdf_bytes(response_json)
            url = self._save_to_drive(pdf_bytes, f"{file_name}_part{i + 1}.pdf")
            urls.append(url)
            last_response = response_json
        logger.info("ラベル分割ダウンロード完了: %d件のPDFを作成しました", len(chunks))
        return {"url": urls[0], "urls": urls, "response_data": last_response}

    def _fetch_labels(self, sku_nums: list[dict[str, Any]]) -> dict[str, Any]:
        payload = {
            "labelType": "STANDARD_FORMAT",
            "marketplaceId": "A1VC38T7YXB528",
            "mskuQuantities": sku_nums,
            "localeCode": "ja_JP",
            "pageType": "A4_40_52x29",
        }
        response = httpx.post(SP_API_LABELS_URL, json=payload, headers=self._headers, timeout=30.0)
        response_json = response.json()
        if response_json.get("errors"):
            messages = "; ".join(f'{e["code"]}: {e["message"]}' for e in response_json["errors"])
            raise RuntimeError(f"SP-API ラベル取得エラー: {messages}")
        if not response_json.get("documentDownloads"):
            raise RuntimeError("SP-API レスポンスにダウンロードURLが含まれていません")
        return response_json

    def _download_pdf_bytes(self, response_json: dict[str, Any]) -> bytes:
        file_uri = response_json["documentDownloads"][0]["uri"]
        response = httpx.get(file_uri, timeout=60.0)
        response.raise_for_status()
        return response.content

    def _save_to_drive(self, pdf_bytes: bytes, file_name: str) -> str:
        from googleapiclient.http import MediaInMemoryUpload
        media = MediaInMemoryUpload(pdf_bytes, mimetype="application/pdf")
        file_metadata = {"name": file_name, "parents": [LABEL_FOLDER_ID]}
        created = self._drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()
        file_id = created["id"]
        return f"https://drive.google.com/uc?export=download&id={file_id}"

    def _split_by_quantity_limit(self, sku_nums: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        total_quantity = sum(item["quantity"] for item in sku_nums)
        needs_split = total_quantity > 15000 or any(item["quantity"] > MAX_QUANTITY_PER_REQUEST for item in sku_nums)
        if not needs_split:
            return [sku_nums]
        expanded: list[dict[str, Any]] = []
        for item in sku_nums:
            remaining = item["quantity"]
            while remaining > 0:
                qty = min(remaining, MAX_QUANTITY_PER_REQUEST)
                expanded.append({"msku": item["msku"], "quantity": qty})
                remaining -= qty
        chunks: list[list[dict[str, Any]]] = []
        current_chunk: list[dict[str, Any]] = []
        chunk_total = 0
        for item in expanded:
            if chunk_total + item["quantity"] > MAX_QUANTITY_PER_REQUEST and current_chunk:
                chunks.append(current_chunk)
                current_chunk = []
                chunk_total = 0
            current_chunk.append(item)
            chunk_total += item["quantity"]
        if current_chunk:
            chunks.append(current_chunk)
        return chunks
