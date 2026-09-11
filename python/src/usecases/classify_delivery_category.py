from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from shared.config import DELIVERY_CATEGORY_REFERENCE_SKUS
from infrastructure.amazon.auth import get_auth_token
from infrastructure.amazon.inbound_plan_creator import InboundPlanCreator
from infrastructure.amazon.merchant_listings_sku_resolver import MerchantListingsSkuResolver
from infrastructure.spreadsheet.sales_sheet import SalesSheet

from domain.shipment.seller_sku import is_usable_sku

from domain.shipment.delivery_category import (
    FASHION,
    NORMAL,
    DeliveryCategoryUndecidable,
    classify_by_cohabitation,
)

logger = logging.getLogger(__name__)

REFERENCE_CATEGORIES = [NORMAL, FASHION]
TRIAL_QUANTITY = 1
MAX_REFERENCE_ATTEMPTS = 3


@dataclass(frozen=True)
class ClassificationOutcome:
    asin: str
    result: "ClassificationResult | None" = None
    error: str = ""


@dataclass(frozen=True)
class ClassificationResult:
    asin: str
    category: str
    inbound_plan_id: str = ""
    written_rows: list[int] | None = None
    skipped: bool = False
    cancel_failed: bool = False


def classify_delivery_category(
    asin: str,
    *,
    sales: Any,
    creator: Any,
    resolve_sku: Callable[[str], str] | None = None,
    overwrite: bool = False,
    dry_run: bool = False,
) -> ClassificationResult:
    target_asin = str(asin).strip()

    existing = sales.load_delivery_category_by_asin().get(target_asin, "")
    if existing and not overwrite:
        logger.info("納品分類は設定済みのためスキップ: ASIN=%s, 分類=%s", target_asin, existing)
        return ClassificationResult(asin=target_asin, category=existing, skipped=True)

    target_sku = _resolve_target_sku(target_asin, sales, resolve_sku)
    reference_pairs = _build_reference_pairs(_reference_candidates(target_sku))

    category, plan_id, cancel_failed = _classify_by_trial_plan(
        target_asin, target_sku, reference_pairs, creator
    )

    if dry_run:
        logger.info("dry-run のため書き込みなし: ASIN=%s, 分類=%s", target_asin, category)
        return ClassificationResult(
            asin=target_asin, category=category, inbound_plan_id=plan_id, cancel_failed=cancel_failed
        )

    written_rows = sales.write_delivery_category(target_asin, category)
    return ClassificationResult(
        asin=target_asin,
        category=category,
        inbound_plan_id=plan_id,
        written_rows=written_rows,
        cancel_failed=cancel_failed,
    )


def _resolve_target_sku(
    asin: str, sales: Any, resolve_sku: Callable[[str], str] | None
) -> str:
    sku = str(sales.load_asin_to_sku_fnsku().get(asin, {}).get("sku", "")).strip()
    if is_usable_sku(sku):
        return sku
    if resolve_sku is not None:
        sku = str(resolve_sku(asin) or "").strip()
    if not is_usable_sku(sku):
        raise RuntimeError(
            f"ASIN {asin} の有効なSKUが解決できません（取得値: {sku or '(空)'}）。"
            "売上/日シートのSKU列を埋めるか、Amazonへの出品登録が終わってから再実行してください"
        )
    return sku


def _reference_candidates(target_sku: str) -> dict[str, list[dict[str, str]]]:
    return {
        category: [{"asin": "", "sku": sku} for sku in skus if sku != target_sku]
        for category, skus in DELIVERY_CATEGORY_REFERENCE_SKUS.items()
    }


def _build_reference_pairs(
    candidates: dict[str, list[dict[str, str]]]
) -> list[dict[str, dict[str, str]]]:
    missing = [category for category in REFERENCE_CATEGORIES if not candidates.get(category)]
    if missing:
        raise RuntimeError(
            f"代表SKUが見つかりません: {', '.join(missing)}。"
            "shared/config.py の DELIVERY_CATEGORY_REFERENCE_SKUS を確認してください"
        )

    pairs: list[dict[str, dict[str, str]]] = []
    for index in range(MAX_REFERENCE_ATTEMPTS):
        pair = {
            category: candidates[category][min(index, len(candidates[category]) - 1)]
            for category in REFERENCE_CATEGORIES
        }
        if pair not in pairs:
            pairs.append(pair)
    return pairs


def _classify_by_trial_plan(
    asin: str,
    sku: str,
    reference_pairs: list[dict[str, dict[str, str]]],
    creator: Any,
) -> tuple[str, str, bool]:
    failures: list[str] = []
    for pair in reference_pairs:
        items = _build_trial_items(asin, sku, pair)
        try:
            plan = creator.create_plan(items)
        except RuntimeError as e:
            failures.append(f"代表={_format_pair(pair)}: {e}")
            logger.warning("試作プラン作成に失敗、次の代表候補を試します: %s", e)
            continue

        plan_id = str(plan.get("inboundPlanId", ""))
        try:
            groups = _to_sku_groups(creator.get_packing_groups(plan_id))
            category = classify_by_cohabitation(
                target_sku=sku,
                reference_skus={c: pair[c]["sku"] for c in REFERENCE_CATEGORIES},
                packing_groups=groups,
            )
        finally:
            cancel_failed = _cancel_quietly(creator, plan_id)

        logger.info("納品分類を判定: ASIN=%s, 分類=%s, 試作プラン=%s", asin, category, plan_id)
        return category, plan_id, cancel_failed

    raise RuntimeError(
        "試作プランを作成できませんでした（全代表候補で失敗）:\n" + "\n".join(failures)
    )


def _build_trial_items(
    asin: str, sku: str, pair: dict[str, dict[str, str]]
) -> dict[str, dict[str, Any]]:
    items = {sku: _trial_item(sku, asin)}
    for reference in pair.values():
        items[reference["sku"]] = _trial_item(reference["sku"], reference["asin"])
    return items


def _trial_item(sku: str, asin: str) -> dict[str, Any]:
    return {"msku": sku, "asin": asin, "quantity": TRIAL_QUANTITY, "labelOwner": "SELLER"}


def _to_sku_groups(packing_groups: list[dict[str, Any]]) -> list[list[str]]:
    return [
        [str(item.get("msku", "")).strip() for item in group.get("items", [])]
        for group in packing_groups
    ]


def _cancel_quietly(creator: Any, plan_id: str) -> bool:
    if not plan_id:
        return False
    try:
        creator.cancel_inbound_plan(plan_id)
        return False
    except Exception as e:
        logger.warning("試作プランのキャンセルに失敗しました（手動削除が必要）: %s / %s", plan_id, e)
        return True


def _format_pair(pair: dict[str, dict[str, str]]) -> str:
    return ", ".join(f"{category}={item['sku']}" for category, item in pair.items())


def run_classification(
    config: Any,
    repo: Any,
    asins: list[str],
    *,
    overwrite: bool = False,
    dry_run: bool = False,
) -> list[ClassificationOutcome]:
    access_token = get_auth_token()
    sales = SalesSheet(repo)
    creator = InboundPlanCreator(auth_token=access_token)
    resolve_sku = _make_sku_resolver(access_token)

    outcomes: list[ClassificationOutcome] = []
    for asin in asins:
        target = str(asin).strip()
        try:
            result = classify_delivery_category(
                target,
                sales=sales,
                creator=creator,
                resolve_sku=resolve_sku,
                overwrite=overwrite,
                dry_run=dry_run,
            )
            outcomes.append(ClassificationOutcome(asin=target, result=result))
        except Exception as e:
            logger.error("納品分類の判定に失敗: ASIN=%s, %s", target, e)
            outcomes.append(ClassificationOutcome(asin=target, error=str(e)))
    return outcomes


def _make_sku_resolver(access_token: str) -> Callable[[str], str]:
    cache: dict[str, str] = {}

    def resolve(asin: str) -> str:
        if asin not in cache:
            resolver = MerchantListingsSkuResolver(auth_token=access_token)
            cache.update(resolver.resolve_skus_by_asins([asin]))
        return cache.get(asin, "")

    return resolve
