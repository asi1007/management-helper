from __future__ import annotations

from datetime import date

from domain.shipment.undelivered_classifier import UndeliveredShipment

INTERNAL_ALIAS_PREFIX = "__PENDING"
MAX_PRODUCT_NAMES = 3


def build_inquiry_message(
    shipments: list[UndeliveredShipment], *, today: date, to_account_id: str,
) -> str:
    if not shipments:
        return ""
    ordered = sorted(shipments, key=lambda s: s.elapsed_days(today) or 0, reverse=True)
    lines = [_header(to_account_id), _intro()]
    lines.extend(_shipment_block(shipment, today) for shipment in ordered)
    lines.append(_footer())
    return "\n".join(line for line in lines if line)


def _header(to_account_id: str) -> str:
    return f"[To:{to_account_id}]徐雪蘭さん" if to_account_id else ""


def _intro() -> str:
    return (
        "お世話になっております。\n"
        "下記の納品分がAmazon倉庫でまだ受領されておりません。\n"
        "配送状況をご確認いただけますでしょうか。\n"
    )


def _shipment_block(shipment: UndeliveredShipment, today: date) -> str:
    elapsed = shipment.elapsed_days(today)
    parts = [f"■ {shipment.shipment_confirmation_id}"]
    if _is_presentable_alias(shipment.plan_alias):
        parts.append(f"  指示書: {shipment.plan_alias}")
    if shipment.shipped_on:
        parts.append(f"  出荷日: {shipment.shipped_on:%Y/%m/%d}（{elapsed}日経過）")
    parts.append(f"  数量: {_quantity_text(shipment)}")
    if shipment.product_names:
        parts.append(f"  商品: {_product_text(shipment.product_names)}")
    if shipment.tracking_number:
        parts.append(f"  追跡番号: {shipment.tracking_number}")
    return "\n".join(parts)


def _is_presentable_alias(alias: str) -> bool:
    return bool(alias) and not alias.startswith(INTERNAL_ALIAS_PREFIX)


def _product_text(product_names: list[str]) -> str:
    shown = product_names[:MAX_PRODUCT_NAMES]
    remainder = len(product_names) - len(shown)
    text = "、".join(shown)
    return f"{text} 他{remainder}件" if remainder > 0 else text


def _quantity_text(shipment: UndeliveredShipment) -> str:
    if shipment.quantity_received > 0:
        return f"発送 {shipment.quantity_shipped}個 / 受領 {shipment.quantity_received}個"
    return f"発送 {shipment.quantity_shipped}個（未受領）"


def _footer() -> str:
    return "\nお手数ですが、追跡番号と現在の配送状況をお知らせください。"
