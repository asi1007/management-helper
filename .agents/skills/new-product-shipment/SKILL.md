---
description: /new-product-shipment コマンド - 初回仕入れ（仕入回数1）の新商品だけを納品指示に出す
alwaysApply: false
---

# /new-product-shipment コマンド

**初回仕入れの商品だけ**を選んで納品指示を出す。まだ一度も納品していないので、
FNSKU の発行漏れ・画像未登録・納品分類の未設定が残りやすく、通常の再仕入れとは確認する点が違う。

## 手順

### 1. 対象を出してユーザーに確認する（**必ず先に出す**）

```bash
cd /Users/wadaatsushi/Documents/automation/procurements/management-helper/python && \
  python3 main.py new-product-shipments
```

「状態 = 梱包依頼必要」かつ「**仕入回数 = 1**」の行を納品分類ごとに出す。**読むだけで何も書き換えない。**

仕入回数は仕入管理シートの **CD列**に値で入っている。行数を数えて判定しない
（在庫切れ行は `com.wada.archive-out-of-stock` が別シートへ退避するので数が合わない）。

結果を表で示し、**実行してよいかユーザーに聞く。** 勝手に送らない。

| 行 | 購入日 | 到着日 | 商品名 | 数量 | SKU/FNSKU |
|---|---|---|---|---|---|

### 2. 出す前に新商品特有の確認をする

| 見るもの | 落ちていたら |
|---|---|
| **SKU / FNSKU** | Amazon から補完する。未発行なら出品登録が終わっていない |
| **納品分類** | `python3 main.py classify-delivery <ASIN>` で Amazon に判定させる |
| **差し止め `18320`** | メイン画像が無い。**ラベルは刷れるが売れない**ので必ず報告する |
| **備考（梱包指示）** | **初回仕入れは高確率で空。** `/suggest-packing` で決めて備考へ書く |

差し止めが出ていても納品自体は進められる（到着までに画像を入れれば売り逃さない）が、
**黙って進めないこと。** 判断はユーザーに委ねる。

**備考が空なのは新商品の常態。** 発注（#5）が梱包方法の決定（#7）より先なので、
初回仕入れの行は備考が空のまま「梱包依頼必要」になる。
2026-09-18 に備考が空のまま2件送ってしまった。現在は指示書生成が止まる。

```bash
cd ../packing-advisor && .venv/bin/python suggest_packing.py <ASIN>   # 候補を出す（決めるのは人）
cd ../packing-advisor && .venv/bin/python suggest_packing.py <ASIN> --set-text "..."
cd ../management-helper/python && python3 main.py sync-remarks --rows <行番号>
```

`suggest_packing.py` が書くのは**売上/日**。指示書が読むのは**仕入管理**なので、
`sync-remarks` で写さないと空のままになる。

### 2-b. 新商品だけが引っかかる2つの停止

**商品準備要件（`FBA_INB_0182`）**

新規 SKU は `prepCategory` が `UNKNOWN` のままで、納品プランの作成が落ちる。
既存商品は全て `NONE` なので揃える。**`prepCategory=NONE` のとき Amazon が受け付ける
`prepTypes` は `[ITEM_NO_PREP]` だけ。**

```bash
POST /inbound/fba/2024-03-20/items/prepDetails
{"marketplaceId": "A1VC38T7YXB528",
 "mskuPrepDetails": [{"msku": "SKU-…", "prepCategory": "NONE", "prepTypes": ["ITEM_NO_PREP"]}]}
```

`/listing` の登録時に入れるのが本来だが、抜けていたら納品前にここで入れる。

**商品画像が 0 枚**

出品直後はカタログに 1 枚も無いことがある。`InstructionSheet._collect_images` が停止する。
**差し止め `18320` が出ていなくても画像が無いことがある**ので、status だけで判断しない。

画像が無いと検品担当が現物を照合できない。**画像を登録してから出すのが既定**
（2026-09-17 にユーザー判断）。急ぐときだけ、商品名で判別してもらう前提で出す。

### 3. 商品が決まったら通常の納品指示に渡す

**専用の送信処理は作らない。** `/request-shipment` と同じ `batch-labels` を使う。

```bash
python3 main.py batch-labels --categories "ノーマル" --rows 255,256 --air
```

**`--rows` で行を絞る。** `--categories` だけだと同じ分類の再仕入れ（海上）まで
空輸で出てしまう。新商品と再仕入れは同じ「ノーマル」に混ざる。

**新商品は `--air`（空輸）が既定。** 初回は売れ方が読めず在庫を切らすと出足でつまずくため、
海上輸送を待たない。プラン別名の末尾に「空輸」が付き、後段の `/confirm-shipment` では
`--lead-days 14` を使う（既定の 1 ヶ月後は海上輸送前提）。

海上でよいと明示されたときだけ `--air` を外す。

### 4. 出したあとは通常と同じ

FC 分割の検知・SKU 照合・指示書とラベルの突合は `batch-labels` が行う。
検証手順は `/request-shipment` を参照。取り消すときは `revert-shipment --alias "MM/DDノーマル空輸"`。

## 注意

- 新商品と再仕入れは同じ納品分類に混ざる。**`--rows` で行番号を指定して分ける**
  （2026-09-18 追加。それまでは分類を書き換えて逃がすしかなかった）
- 初回は納品分類が空のことがある。空のまま `batch-labels` に渡すと「未分類」グループになり、
  `--categories` で指定できない
