from __future__ import annotations


def is_usable_sku(sku: str | None) -> bool:
    # 形式では仮SKUかどうかを判定しない。
    # create_listing.py は SKU-YYYYMMDDHHmmss を本番SKUとして Amazon に登録しており、
    # 出品レポートで SKU-20260830090814 も SKU-20260508124233 も実在を確認した（2026-09-03）。
    # 形式で弾いていたため新商品の納品分類が必ず落ちていた（B0HH5DR13D）。
    # 実在しないSKUは createInboundPlan が Amazon 側のエラーで弾く。
    value = str(sku or "").strip()
    if not value:
        return False
    # 売上/日のSKU列は xlookup なので、未登録の商品は #N/A や #REF! になる
    return not value.startswith("#")
