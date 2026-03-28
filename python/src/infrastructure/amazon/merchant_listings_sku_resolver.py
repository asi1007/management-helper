from __future__ import annotations

import gzip
import logging
import time

import httpx

logger = logging.getLogger(__name__)

REPORTS_API_BASE = "https://sellingpartnerapi-fe.amazon.com/reports/2021-06-30"
MARKETPLACE_ID = "A1VC38T7YXB528"
POLL_INTERVAL_SEC = 5
POLL_TIMEOUT_SEC = 90

EN_SKU_HEADER = "seller-sku"
EN_ASIN_HEADER = "asin1"
JA_SKU_HEADER = "出品者SKU"
JA_ASIN_HEADER = "ASIN1"


class MerchantListingsSkuResolver:
    def __init__(self, auth_token: str) -> None:
        self._auth_token = auth_token
        self._headers = {
            "Accept": "application/json",
            "x-amz-access-token": auth_token,
            "Content-Type": "application/json",
        }

    def resolve_skus_by_asins(self, asins: list[str]) -> dict[str, str]:
        report_id = self._create_merchant_listings_report()
        document_id = self._wait_report_done_and_get_document_id(report_id)
        text = self._download_report_document_text(document_id)
        return self._extract_asin_sku_map(text, asins)

    def _create_merchant_listings_report(self) -> str:
        url = f"{REPORTS_API_BASE}/reports"
        payload = {"reportType": "GET_MERCHANT_LISTINGS_ALL_DATA", "marketplaceIds": [MARKETPLACE_ID]}
        response = httpx.post(url, json=payload, headers=self._headers, timeout=30.0)
        response.raise_for_status()
        report_id = response.json()["reportId"]
        logger.info("レポート作成: %s", report_id)
        return report_id

    def _wait_report_done_and_get_document_id(self, report_id: str) -> str:
        url = f"{REPORTS_API_BASE}/reports/{report_id}"
        elapsed = 0
        while elapsed < POLL_TIMEOUT_SEC:
            response = httpx.get(url, headers=self._headers, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            status = data.get("processingStatus", "")
            if status == "DONE":
                document_id = data.get("reportDocumentId", "")
                logger.info("レポート完了: documentId=%s", document_id)
                return document_id
            if status in ("CANCELLED", "FATAL"):
                raise RuntimeError(f"レポートが失敗しました: {status}")
            time.sleep(POLL_INTERVAL_SEC)
            elapsed += POLL_INTERVAL_SEC
        raise TimeoutError(f"レポートがタイムアウトしました ({POLL_TIMEOUT_SEC}秒)")

    def _download_report_document_text(self, document_id: str) -> str:
        url = f"{REPORTS_API_BASE}/documents/{document_id}"
        response = httpx.get(url, headers=self._headers, timeout=30.0)
        response.raise_for_status()
        doc = response.json()
        download_url = doc.get("url", "")
        compression = doc.get("compressionAlgorithm", "")
        dl_response = httpx.get(download_url, timeout=60.0)
        dl_response.raise_for_status()
        content = dl_response.content
        if compression == "GZIP":
            content = gzip.decompress(content)
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            return content.decode("shift_jis")

    def _extract_asin_sku_map(self, tsv_text: str, asins: list[str]) -> dict[str, str]:
        asin_set = set(asins)
        lines = tsv_text.strip().split("\n")
        if not lines:
            return {}
        headers = lines[0].split("\t")
        headers_lower = [h.strip().lower() for h in headers]
        sku_col = self._find_column(headers, headers_lower, [EN_SKU_HEADER, JA_SKU_HEADER])
        asin_col = self._find_column(headers, headers_lower, [EN_ASIN_HEADER, JA_ASIN_HEADER])
        if sku_col is None or asin_col is None:
            logger.warning("SKUまたはASIN列が見つかりません: %s", headers)
            return {}
        result: dict[str, str] = {}
        for line in lines[1:]:
            cols = line.split("\t")
            if len(cols) <= max(sku_col, asin_col):
                continue
            asin = cols[asin_col].strip()
            sku = cols[sku_col].strip()
            if asin in asin_set and sku and asin not in result:
                result[asin] = sku
        return result

    def _find_column(self, headers: list[str], headers_lower: list[str], candidates: list[str]) -> int | None:
        for candidate in candidates:
            candidate_lower = candidate.lower()
            for i, h in enumerate(headers_lower):
                if h == candidate_lower:
                    return i
            for i, h in enumerate(headers):
                if h.strip() == candidate:
                    return i
        return None
