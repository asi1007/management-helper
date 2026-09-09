---
description: /delivery-status コマンド - 仕入から納品までの滞留を3工程に分けて一覧する
alwaysApply: false
---

# /delivery-status コマンド

「今どこで止まっているか」を工程ごとに出す。**読むだけで何も書き換えない。**

```bash
cd /Users/wadaatsushi/Documents/automation/procurements/management-helper/python && \
  python3 main.py delivery-status
```

| オプション | 既定 | 説明 |
|---|---|---|
| `--stale-days` | 14 | この日数を超えた行に `⚠️` を付け、見出しに件数を出す |

## 3つの工程

仕入管理シートの**列の値**から判定する（`domain/shipment/delivery_stage.py`）。

| 工程 | 条件 | まとめる単位 | 経過日数の起点 |
|---|---|---|---|
| **イーウー到着待ち** | 到着日が空 | 注文番号 | 購入日 |
| **発送指示待ち** | 到着日あり・発送日が空 | 納品分類 | 到着日 |
| **Amazon倉庫到着待ち** | 発送日あり・受領日が空 | プラン別名 | 発送日 |

受領日が入っているか**在庫数が入っていれば受領済み**として除外する。
受領日は入れ忘れがあるが、在庫が立っていれば Amazon には入っている。

### 「状態」列は判定に使わない

状態は他列から導出される `ifs` 数式なので、入力条件にすると
「状態が決まらないから処理されない → 列が埋まらないから状態が決まらない」で循環する。
過去に `TARGET_STATUSES` で同じ罠を踏んでいる。**列の値を直接見ること。**

## 何を見るか

- **イーウー到着待ち**: 14日を超えたら `/update-arrival` が Todoist へ積む。
  買付完了日が空のまま止まっていることがあるので、長いものは Chatwork で確認する
- **発送指示待ち**: `/request-shipment` の対象。納品分類ごとに納品プランが分かれる
- **Amazon倉庫到着待ち**: `/confirm-shipment` 済みで受領待ち。
  受領されているのにシートが空なだけのことも多いので、まず `main.py update-status` を流す

## 似たコマンドとの違い

| コマンド | 見るもの |
|---|---|
| `delivery-status` | **全工程**。今どこに何個溜まっているか |
| `inquire-undelivered` | Amazon 未受領のみ。SP-API で受領数まで照合し、Chatwork へ問い合わせ文を送れる |
| `/update-arrival`（automate-yiwu） | イーウー未到着のみ。到着日を埋め、遅延を daily note と Todoist へ出す |

`delivery-status` は一覧するだけなので、**問い合わせや書き込みは上の2つを使う**。
