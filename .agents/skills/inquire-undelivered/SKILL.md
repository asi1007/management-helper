---
description: /inquire-undelivered コマンド - Amazon倉庫に未受領のまま滞留している納品を洗い出し、Chatworkで配送状況を問い合わせる
alwaysApply: false
---

# /inquire-undelivered コマンド

発送済みなのに Amazon FC で受領されていない納品を抽出し、長期滞留分について
Chatwork（徐雪蘭さん宛）へ配送状況の問い合わせを送るコマンド。

## 実行

```bash
# 確認のみ（送信しない）
cd /Users/wadaatsushi/Documents/automation/procurements/management-helper/python && \
  python3 main.py inquire-undelivered

# 文案を確認したうえで送信
python3 main.py inquire-undelivered --send
```

| オプション | 既定値 | 説明 |
|---|---|---|
| `--threshold-days` | 21 | 出荷からこの日数を超えて未受領なら問い合わせ対象 |
| `--send` | off | 付けると Chatwork へ送信。**付けない限り送信しない** |

**必ず一度 `--send` なしで実行し、文案を確認してから送信すること。**

## 抽出条件

仕入管理シートから次の行を拾い、納品番号（`FBA...`）単位で集約する。

- 「発送日」が入っている
- 「受領日」が空
- 「納品プラン」が入っている

## 判定区分

集約した納品ごとに SP-API で `shipmentStatus` と `QuantityShipped/QuantityReceived` を取得して分類する。

| 区分 | 条件 | 扱い |
|---|---|---|
| **受領済み** | `status == CLOSED` または 受領率 90%以上 | 問い合わせ不要。`update-status` を回せばシートの受領日が埋まる |
| **輸送中** | 経過日数 < `--threshold-days` | 様子見 |
| **要問い合わせ** | 経過日数 ≥ `--threshold-days` かつ未受領 | Chatwork 文案に載せる |
| **発送日が不正** | 発送日が空 or 未来日付 | シートの修正が必要 |

受領判定を先に見るため、**シート上「未受領」でも実際は受領済みのケースが多い**。
その場合は問い合わせではなく `update-status` の実行が正しい対応。

## 問い合わせ文の内容

納品番号ごとに、経過日数の長い順で以下を列挙する。

- 納品番号（`shipmentConfirmationId`）
- 指示書名（プラン別名）
- 出荷日と経過日数
- 発送数量／受領数量
- 商品名（最大3件、超過分は「他N件」）
- 追跡番号（シートに入っていれば）

**`__PENDING_...__` のような内部プレースホルダのプラン別名は出力しない**
（`fill-sku-fnsku` が仮置きする値で、社外に出すと意味が通じないため）。

## 注意事項

- 中国（義烏）からの海上輸送は発送から受領まで概ね 15〜40 日かかる。既定21日は
  「そろそろ確認したい」ラインであり、超過即異常ではない
- 自宅発送分（プラン別名が `自宅`）も対象に入る。こちらは徐さんではなく自分の発送なので、
  文案に混ざっていたら手動で除くこと
- 実行しても**シートは一切書き換えない**（読み取りと Chatwork 送信のみ）
