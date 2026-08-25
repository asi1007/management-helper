from __future__ import annotations

NORMAL = "ノーマル"
FASHION = "ファッション"
HOME = "自宅"


class DeliveryCategoryUndecidable(RuntimeError):
    pass


def classify_by_cohabitation(
    target_sku: str,
    reference_skus: dict[str, str],
    packing_groups: list[list[str]],
) -> str:
    normalized_groups = [{str(sku).strip() for sku in group} for group in packing_groups]
    target = str(target_sku).strip()

    target_group = _find_group(target, normalized_groups)
    if target_group is None:
        raise DeliveryCategoryUndecidable(
            f"対象SKU {target} が試作プランの packingGroup に含まれていません"
        )

    group_by_category = _resolve_reference_groups(reference_skus, normalized_groups)
    _reject_cohabiting_references(group_by_category)

    cohabiting = [
        category for category, index in group_by_category.items() if index == target_group
    ]
    if not cohabiting:
        raise DeliveryCategoryUndecidable(
            f"対象SKU {target} はどの代表SKUとも同居しませんでした。"
            f"新しい納品分類が必要な可能性があります（代表: {reference_skus}）"
        )
    return cohabiting[0]


def _find_group(sku: str, groups: list[set[str]]) -> int | None:
    for index, group in enumerate(groups):
        if sku in group:
            return index
    return None


def _resolve_reference_groups(
    reference_skus: dict[str, str], groups: list[set[str]]
) -> dict[str, int]:
    resolved: dict[str, int] = {}
    for category, sku in reference_skus.items():
        index = _find_group(str(sku).strip(), groups)
        if index is not None:
            resolved[category] = index
    if not resolved:
        raise DeliveryCategoryUndecidable(
            f"代表SKUが試作プランの packingGroup に1つも含まれていません（代表: {reference_skus}）"
        )
    return resolved


def _reject_cohabiting_references(group_by_category: dict[str, int]) -> None:
    indexes = list(group_by_category.values())
    if len(indexes) != len(set(indexes)):
        raise DeliveryCategoryUndecidable(
            f"代表SKUどうしが同じ packingGroup に入りました。"
            f"代表SKUの選定が誤っている可能性があります（{group_by_category}）"
        )
