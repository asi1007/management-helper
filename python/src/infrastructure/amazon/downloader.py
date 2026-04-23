from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SP_API_LABELS_URL = "https://sellingpartnerapi-fe.amazon.com/inbound/fba/2024-03-20/items/labels"
MAX_QUANTITY_PER_REQUEST = 999


class Downloader:
    def __init__(self, auth_token: str, save_dir: Path) -> None:
        self._auth_token = auth_token
        self._save_dir = save_dir
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
        path = self._save_to_local(pdf_bytes, f"{file_name}.pdf")
        return {"path": str(path), "response_data": response_json}

    def _download_multiple_batches(self, chunks: list[list[dict[str, Any]]], file_name: str) -> dict[str, Any]:
        paths: list[str] = []
        last_response: dict[str, Any] = {}
        for i, chunk in enumerate(chunks):
            logger.info("ラベル分割ダウンロード: %d/%d", i + 1, len(chunks))
            response_json = self._fetch_labels(chunk)
            pdf_bytes = self._download_pdf_bytes(response_json)
            path = self._save_to_local(pdf_bytes, f"{file_name}_part{i + 1}.pdf")
            paths.append(str(path))
            last_response = response_json
        logger.info("ラベル分割ダウンロード完了: %d件のPDFを作成しました", len(chunks))
        return {"path": paths[0], "paths": paths, "response_data": last_response}

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

    def _save_to_local(self, pdf_bytes: bytes, file_name: str) -> Path:
        self._save_dir.mkdir(parents=True, exist_ok=True)
        file_path = self._save_dir / file_name
        file_path.write_bytes(pdf_bytes)
        logger.info("ラベルPDF保存: %s", file_path)
        return file_path

    def _split_by_quantity_limit(self, sku_nums: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        SPLIT_THRESHOLD = 15000
        CHUNK_LIMIT = 10000
        total_quantity = sum(item["quantity"] for item in sku_nums)
        if total_quantity <= SPLIT_THRESHOLD:
            return [sku_nums]
        chunks: list[list[dict[str, Any]]] = []
        current_chunk: list[dict[str, Any]] = []
        chunk_total = 0
        for item in sku_nums:
            if chunk_total + item["quantity"] > CHUNK_LIMIT and current_chunk:
                chunks.append(current_chunk)
                current_chunk = []
                chunk_total = 0
            current_chunk.append(item)
            chunk_total += item["quantity"]
        if current_chunk:
            chunks.append(current_chunk)
        return chunks
