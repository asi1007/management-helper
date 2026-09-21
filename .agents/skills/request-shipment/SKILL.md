---
description: /request-shipment コマンド - 梱包依頼必要の行を納品分類グループごとにラベル+指示書を一括作成し、Chatworkで送付
alwaysApply: true
---

# /request-shipment コマンド

ユーザが `/request-shipment` と入力した場合、以下を実行する。

## 事前確認: FC 分割 (自動化済み)

`/request-shipment` は実行時に各グループで SP-API 試作プランを作成し、`packingGroups` を取得して FC 分割を事前検知する。

### 自動的な動作

- **1 packingGroup (分割なし)**: 「納品プラン」列に試作プラン URL を `=HYPERLINK(...)` で書き込み、そのままラベル生成・指示書作成・Chatwork送信に進む。後段 `/apply-inspection` でこの試作プランが再利用される。
- **2+ packingGroups (分割あり)**: 全グループ走査後に RuntimeError で停止。各 SKU の振り分けを表示。ラベルPDF・指示書・Chatwork送信は一切実行されない (all-or-nothing 方針)。

### 分割検知時のメッセージ例

```
⚠️ FC分割を検知しました。

[ノーマル] 試作プラン: wf52345... (2グループに分割)
  グループ1 (pg-aaa): 行340, 352, 353 (3 SKUs)
  グループ2 (pg-bbb): 行357, 359, 360 (3 SKUs)
  プランURL: https://sellercentral.amazon.co.jp/fba/sendtoamazon/confirm_content_step?wf=wf52345...

RuntimeError: FC分割を検知 (1グループ)。仕入管理シートの「納品分類」列をグループ別に書き換えてから再実行してください。
```

### 分割時の対処 (2026-07-28 標準手順)

FC分割検知で停止したら、以下を **必ず** 実行する（ユーザ確認不要、機械的に対応する）:

1. **各 packingGroup の SKU/行番号を確認** (エラーメッセージに表示済み)
2. **AskUserQuestion で書き換え方針だけ確認** (例: 少数派グループを `分類2`、多数派を `分類1` にする等):
   ```
   グループ1 (3 SKU): 行441/447/453
   グループ2 (1 SKU): 行436
   → 行436をファッション2、行441/447/453をファッション1 でよいか？
   ```
3. **納品分類列を Python で自動書き換え**:
   ```python
   from src.infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
   from src.infrastructure.spreadsheet.purchase_sheet import PurchaseSheet
   import os
   from dotenv import load_dotenv; load_dotenv()

   repo = BaseSheetsRepository(credentials_file=os.getenv('GOOGLE_CREDENTIALS_FILE'))
   sheet = PurchaseSheet(repo=repo, sheet_id=os.getenv('SHEET_ID'), sheet_name=os.getenv('PURCHASE_SHEET_NAME'))
   category_col = sheet._headers.index('納品分類') + 1

   # ユーザ承認の割り振りで書き換え
   sheet.write_cell(436, category_col, 'ファッション2')
   for r in [441, 447, 453]:
       sheet.write_cell(r, category_col, 'ファッション1')
   ```
4. **`/request-shipment --categories "元分類1,元分類2,..."` で全グループ再実行** (分割前グループを新分類名で置き換え、他グループは重複記載しても問題なし)
5. 古い試作プランは Seller Central で手動削除 (SP-API `cancelInboundPlan` は未実装)。次回 `/apply-inspection` で新試作プランが自動再利用される

## 実行手順

1. まずグループ一覧と各行の詳細（商品名・数量）を表示してユーザに確認する:

```bash
cd /Users/wadaatsushi/Documents/automation/procurements/management-helper/python && python3 -c "
from src.shared.config import AppConfig
from src.infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from src.infrastructure.spreadsheet.purchase_sheet import PurchaseSheet
from collections import defaultdict

config = AppConfig.from_dotenv()
repo = BaseSheetsRepository(config.credentials_file)
sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
sheet.filter('状態', ['梱包依頼必要'])

groups = defaultdict(list)
for row in sheet.data:
    cat = str(row.get('納品分類') or '').strip() or '未分類'
    groups[cat].append(row)

for cat, rows in groups.items():
    total_qty = sum(int(str(r.get('購入数') or '0').strip() or '0') for r in rows)
    print(f'\n=== {cat} ({len(rows)}行, 合計{total_qty}個) ===')
    for r in rows:
        title = str(r.get('商品名') or '').strip()[:45]
        qty = str(r.get('購入数') or '').strip()
        purchase_date = str(r.get('購入日') or '').strip()[:10]  # YYYY-MM-DD or MM-DD
        print(f'  行{r.row_number}: {purchase_date} | {title} | 数量:{qty}')
"
```

結果は以下の表形式で表示すること（**購入日を必ず含める**、購入日の古い順に依頼可否を判断する材料になる）:

| グループ | 行 | 購入日 | 商品名 | 数量 |
|---------|-----|-------|-------|------|
| **グループ名** (N行, 合計X個) | | | | |
| | 行番号 | YYYY-MM-DD | 商品名（短縮） | 数量 |

2. ユーザが処理するグループを選択したら、`--categories` オプションで指定して実行する:

```bash
cd /Users/wadaatsushi/Documents/automation/procurements/management-helper/python && python3 main.py batch-labels --categories "ノーマル,ファッション"
```

- `--categories` にカンマ区切りで納品分類名を指定
- 省略すると全グループ（自宅を除く）を処理
- **CLI サブコマンド名は `batch-labels` のまま**（2026-08-25 にスラッシュコマンドのみ `/request-shipment` へ改称）。`main.py request-shipment` は存在しない

## 処理内容

1. 仕入管理シートから「状態」=「梱包依頼必要」の行を抽出
2. 「納品分類」でグループ化し、指定グループのみ処理
3. **SKU/FNSKU検証** (`_validate_sku_fnsku`, 2026-05-18 強化):
   - SKU が空 → エラー停止
   - **FNSKU が空 → エラー停止** (旧仕様では見逃していた)
   - **SKU が仮SKU形式 (`SKU-\d{10,}`) → エラー停止** (例: `SKU-20260508124233`、Amazon側で正規SKU未発行の状態)
   - エラーメッセージは行番号付きで全件報告。Amazon側でSKU/FNSKU発行後に再実行
4. **同一 SKU の行を集約** (`InstructionSheet._extract_rows` および `create_inspection_sheet._collect_matched_items`):
   - **指示書 xlsx** (`0517XX指示書.xlsx`): 同 SKU 複数行を 1 行集約 (数量合算、備考・注文番号は重複排除連結)。集約キーは SKU、SKU 空欄は FNSKU。
   - **検品指示書 xlsx** (`0517XX検品指示書.xlsx`): 同 ASIN+SKU 複数行を 1 アイテム集約 (数量合算、注文番号連結)。これにより同 ASIN の詳細指示書シートが `_2`/`_3` と複数追加されるのを防ぐ → ファイルサイズ縮小 (実績: 31MB → 10MB)。
   - 上記改修は 2026-05-17 のもの (`tests/infrastructure/spreadsheet/test_instruction_sheet_aggregate.py`, `tests/usecases/test_inspection_collect_aggregate.py` で TDD 済み)
5. **自宅グループ**: 指示書xlsxのみ生成（ラベルPDF・検品指示書はスキップ）
6. **その他グループ**: ラベルPDF + 指示書xlsx + 検品指示書を生成（Google Drive共有フォルダに保存）
   - ラベルPDF分割: SP-API の制限に合わせ、1 SKU あたり 10,000 個・1 リクエスト 100 SKU までに分割（`fulfillmentInbound_2024-03-20` の `MskuQuantity.quantity` maximum=10000 / `mskuQuantities` maxItems=100）。超えた分は `_part2.pdf` 以降に分かれる
7. 梱包依頼日・プラン別名をシートに書き込み
8. 集計出力（重量×購入数、送料×購入数、関税×購入数）
9. Chatworkにグループごとにメッセージ+ファイルを送信（[To:986396]徐雪蘭さん宛）

## 売上/日シートの SKU・fnsku は数式ではなくマスタ (2026-09-07)

以前は SKU 列が `=ARRAYFORMULA(xlookup(A{行},'マネジメント'!$A$4:A,'マネジメント'!$B$4:B))` で、
**別シートの写しだった**。参照先が誤っていると気づけないまま全工程へ伝播する。
2026-09-07 に **76 行すべてを値に固定**した（数式 0 件 / 空 0 件 / Amazon と不一致 0 件）。

- `fill_missing_sku_fnsku_from_sales` はこのシートを見るので、**ここが SKU の正本**
- **新商品を足したときは SKU・fnsku を自分で埋めること。** 数式が無いので自動では入らない
- 値は Amazon の `listings/2021-08-01/items/{sellerId}` から引く。**シートを根拠にしない**

### 同一 ASIN に新品 SKU と中古 SKU が並存する

`B0FCHM6QQR` は `DB-T0OT-ZDCG`（new_new）と `USED-B0FCHM6QQR`（used_like_new）を持つ。
ASIN だけで SKU を決めると**中古 SKU を掴む**。補完するときは `conditionType` が `new` で
始まるものだけを候補にし、**シートに有効な SKU が既にあるならそれを優先する**。

## SKU が本当にその商品か Amazon に確かめる (2026-09-07)

**ラベル PDF と 指示書 xlsx は別のソースから作られる。**

| 成果物 | FNSKU の出どころ |
|---|---|
| ラベル PDF | **SKU を SP-API に渡して Amazon が生成** |
| 指示書 xlsx | **仕入管理シートの FNSKU 列** |

そのためシートの SKU が別商品を指していても、**両方それらしく出来上がって誰も気づかない**。
指示書には正しい FNSKU が印字され、ラベルだけが別商品になる。

`_validate_sku_identity` が全 SKU を `listings/2021-08-01/items/{sellerId}/{sku}` で引き、
**シートの ASIN・FNSKU と一致しなければ RuntimeError で停止**する（行番号付きで全件report）。

### 2026-09-04 の事故

売上/日シートの `B0G1J3NW6Y`（ジュエリー鑑定用ルーペ40倍）の SKU 列に
**別商品 `XM-ZLBK-D2DZ`（2L版アクリルフォトフレーム）が入っていた**。
`fill_missing_sku_fnsku_from_sales` はこれを検証せず仕入管理へコピーし、
ラベル 800 枚が `X001AFD3G7`（フォトフレームの FNSKU）で刷られて検品担当へ渡った。

- 指示書 xlsx の FNSKU 列はシートの値 `X001BZE9Q9` で**正しく見えていた**
- 実行後の検証は**ページ数しか見ていなかった**ため通過した
- 同じ誤りは 2025-11-30 の行にも既に存在しており、**シートに前からあった誤りを広げた**

**ASIN と SKU の対応は Amazon が正。シートは写しにすぎない。**
シートを根拠に SKU を決めてはいけない。

## 指示書に商品写真が無ければエラーで停止する (2026-09-04 / 2026-09-21 拡張)

指示書 xlsx の A 列には商品写真が必ず入る。**1 ASIN でも欠ければ `MissingProductImageError` で停止**し、
ラベル PDF も Chatwork 送信も走らない。検品担当は写真で現物を照合するため、写真なしの指示書は送れない。

検知は 3 段構え。「取れなかった」だけでなく「取れたが写真として使えない」「貼られなかった」も止める。

| # | 何を見るか | 捕まえるもの |
|---|---|---|
| 1 | 全行の ASIN に画像が揃っているか (`find_rows_without_image`) | カタログ未反映・ダウンロード失敗・ASIN 空欄 |
| 2 | 取れたバイト列が写真として成立しているか (`is_usable_product_image`) | 43 バイトの透明 GIF、HTML のエラーページ、壊れた断片 |
| 3 | 保存した xlsx に行数ぶん埋め込まれたか (`count_embedded_images`) | 1・2 が通っても貼り付けに失敗したケース |

- **2 が GIF を弾くのは意図的。** Amazon のカタログ画像は jpg / png で来るので、GIF が届いた時点で偽物。
  `images-na.ssl-images-amazon.com/images/P/{ASIN}...` は 200 を返すが実体は 43 バイトの透明 GIF
- **3 はテンプレート自身の画像 1 枚を差し引いて数える** (`template_image_count`)。テンプレを差し替えても追従する
- **止めたときは保存途中のファイルを消す。** 写真なしの指示書がフォルダに残ると誤って配ってしまう
- エラーには**仕入管理シートの行番号と ASIN** が並ぶので、そのまま直しに行ける

画像は次の順で解決する。

1. **Keepa** (`imagesCSV` → `images[0].m/l`)
2. **SP-API カタログ** (`catalog/2022-04-01/items/{asin}?includedData=images` の `variant=MAIN`)

**新規出品直後は両方とも空になる。** Amazon のカタログに反映されるまで数時間かかるため、
出品・画像登録の当日に梱包依頼を出すと止まる。止まったら反映を待って再実行する。

### 自宅グループも止める (2026-09-21 変更)

以前は自宅納品だけ `require_images=False` で、写真が取れなくても警告だけ出して指示書を作っていた。
「事務所へ送るだけで FNSKU ラベルも検品指示書も作らないから、写真が無くても作業は成立する」という理由だったが、
**写真の入っていない指示書が出てしまう唯一の経路**でもあった。引数ごと廃止し、全グループで一律に止める。

## 指示書の項目が空欄なら出さずに止める (2026-09-18)

指示書 xlsx に書く **FNSKU・ASIN・数量・備考・注文番号**のどれかが空なら
`BlankInstructionFieldError` で停止する。行番号と空だった列名が出る。

**とくに備考は梱包指示そのもの。** 「OPP袋に N 枚入れて FNSKU シールを貼る」のような
作業内容がここにしか書かれていない。空のまま出すと検品担当は梱包方法を知らされないまま
現物だけ受け取ることになる。**備考が空なのは、梱包方法がまだ決まっていないという意味**なので、
`/suggest-packing` で決めて仕入管理シートの備考へ書いてから出し直す。

2026-09-18、新商品2件（キーリングハンガー・バイク用エアーバルブ 各700個）を
備考が空のまま送ってしまった。新商品は発注が梱包方法の決定より先に進むため、
**初回仕入れの行は備考が空のまま「梱包依頼必要」になる。**

**FNSKU が無い行は空欄にすらならず、指示書から丸ごと消える。**
`_extract_rows` が読み飛ばすため、その商品が抜けても気づけない。
これも `find_dropped_rows` で同じエラーにまとめて止める。

検証は `InstructionSheet.create` にあるので `/request-shipment` と `print-labels` の
どちらの経路でも効く。列を増やしたら `REQUIRED_ROW_FIELDS` にも足すこと。

## 備考は売上/日が正本。仕入管理へは `sync-remarks` で写す (2026-09-18)

梱包指示（備考）を書くのは `/suggest-packing` で、書き先は**売上/日**。
仕入管理へは**発注時に `auto-order` がコピーする**だけなので、
発注より後に梱包方法を決めた行は仕入管理側が空のまま残る。

**新商品は構造的に必ずこれに当たる。** 発売フローで発注は #5、梱包方法の決定は #7 だから。

```bash
python3 main.py sync-remarks --rows 255,256 --dry-run   # 対象を確認
python3 main.py sync-remarks --rows 255,256
```

**既存の備考は上書きしない**（`--overwrite` を付けたときだけ）。仕入管理の備考はロット別で、
同じ商品でも行ごとに違う（行189は「带卡位 磨砂」、行190は「带卡位 透明」）。
一括で上書きすると別ロットの指示が消える。

## 自動検証 (実行時に常時、2026-05-19 強化)

`/request-shipment` は実行中に以下の検証を自動実行する。乖離があれば RuntimeError で停止し、ユーザー確認が促される。

### A. 依頼対象漏れ検知 (`_detect_missing_rows`)

「梱包依頼必要」状態でフィルタした行のうち、何らかの理由で処理から漏れた行を最後に検出。漏れがあれば行番号付きで報告。
**現実装**: `_validate_sku_fnsku` を最初に走らせて SKU/FNSKU 空 or 仮 SKU 単独 (FNSKU 無し) を検出するため、漏れは事前にエラーで止まる。utility として `_detect_missing_rows(requested_rows, processed_row_numbers)` も提供 (将来用)。

### B. ラベル PDF ページ数 vs 指示書数量 検証 (`_verify_label_quantity` + `_check_label_pdf_pages`)

ラベル PDF を生成した直後、各 PDF のページ数を `pypdf` (フォールバック: macOS の `mdls`) で取得し、SKU別 `ceil(qty/40)` 合計と比較する。

| 検証 | 計算 |
|---|---|
| 期待ページ数 | `Σ ceil(各SKU.qty / 40)` |
| 実ページ数 | 全 PDF の合計 |
| 許容差 | `max(期待×20%, 2)` ページ |
| 許容内 | OK |
| 許容超 | **RuntimeError + 標準エラー出力に `⚠️ [category] ...` 表示** |

過去の事例:
- 2026-05-17 ノーマル: 期待 451 vs 実 451 ✅
- 2026-05-19 ノーマル20行: 期待 415 vs 実 413 ✅ (-2 端数)

エラー時の調査ポイント (再掲):
1. `InstructionSheet._extract_rows` の SKU 集約 (同 SKU が別エントリで来てないか)
2. `LabelAggregator.aggregate` の SKU 集約 (同上)
3. `Downloader._split_by_quantity_limit` のチャンク分割で SKU が分断されてないか
4. SP-API 応答に欠落 SKU がないか

## 実行後の検証 (必須)

`/request-shipment` が終わったら、**必ず**指示書 xlsx の数量とラベル PDF のページ数が想定通りかを確認する。Amazon に送るラベル PDF は **1ページ=40ラベル** なので、合計数 / 40 (切り上げ) が期待ページ数。

### 確認手順

```bash
DRIVE="/Users/wadaatsushi/Library/CloudStorage/GoogleDrive-zyanzyakazyan@gmail.com/マイドライブ/work/shop/invoices/0828 ■共有 新白岡輸入販売×TAXLAB/業務用書類/8.指示書"

# 1. 指示書 xlsx の数量合計を抽出 (集約後の数量を Sum、自宅以外)
python3 -c "
from openpyxl import load_workbook
for grp in ['ファッション1', 'ファッション2']:
    fn = f'$DRIVE/検品指示書/0517{grp}指示書.xlsx'  # 0517 は実行日
    wb = load_workbook(fn)
    ws = wb.active
    total = 0
    for row in ws.iter_rows(min_row=8, values_only=True):
        q = row[3]
        if isinstance(q, (int, float)):
            total += int(q)
    print(f'{grp}: 指示書数量合計 = {total}')
"

# 2. ラベル PDF のページ数を確認 (1ページ=40枚)
for grp in ファッション1 ファッション2; do
  f="$DRIVE/ラベル/2026-05-17_${grp}.pdf"  # 日付は実行日
  pages=$(mdls -name kMDItemNumberOfPages -raw "$f")
  echo "$grp: PDF pages=$pages"
done
```

### 検証ロジック

ラベル PDF はラベルが**SKU 単位で配置**され、各 SKU の最終ページが 40枚未満なら半端ページが余る。そのため正確な期待値は **SKU 単位の `ceil(qty/40)` 合計**:

```python
from openpyxl import load_workbook
import math
wb = load_workbook('検品指示書.xlsx')
ws = wb.active
expected = 0
for row in ws.iter_rows(min_row=8, values_only=True):
    qty = row[3]
    if isinstance(qty, (int, float)) and qty > 0:
        expected += math.ceil(qty / 40)
print(f'期待ページ計={expected}')
```

| 検証 | 計算式 |
|---|---|
| 単純合計 (集計用 = ざっくり下限) | `ceil(数量合計 / 40)` |
| **正確な期待値** | `Σ ceil(各SKUの数量 / 40)` |
| OK | 実ページ数 == 正確な期待値 |
| 1〜数ページ程度差あり | SKU の枚数端数や ラベル分割 part 境界の半端ページの可能性、許容 |
| 大幅に差 (>20%) | 集約バグ or ラベル分割漏れの可能性、原因調査要 |

例 (ノーマル 2026-05-17): 数量合計 17,500、SKU 17行 → 単純計算 438、SKU単位計算で実際 451 ≈ 438+13 (端数分)。

### 検証で NG が出た場合

- 数量と PDF ページが合わない → `InstructionSheet._extract_rows` のSKU集約と `Downloader` のラベル分割ロジック (1 SKU 10,000個・1リクエスト100 SKU で分割) を疑う
- 指示書 xlsx の数量と仕入管理シート「購入数」が合わない → SKU集約キー (SKU 空欄時は FNSKU fallback) の挙動を確認
- 修正後は **Chatwork 送付済みを取り下げ → 再実行** (下記「再実行する場合」参照)

### Chatwork ファイル送付エラー対処 (10MB超)

Chatwork のファイル添付制限は **10MB**。検品指示書 (詳細指示書シートが多数追加されると数十MB) は超えやすい。送信時のエラーログ例:

```
Chatworkファイルエラー (0517ノーマル検品指示書.xlsx): 413 HTTP content length exceeded 10485760 bytes.
```

対処手順:

1. **Drive 共有リンクで送る** (推奨、ファイル自体は Drive 上にあるため):
   ```python
   # Drive ファイル ID を取得 (例: Google Drive MCP search_files で title 指定)
   # URL 形式: https://drive.google.com/file/d/{file_id}/view
   import requests, os
   from dotenv import load_dotenv; load_dotenv()
   room_id = os.getenv('CHATWORK_ROOM_ID')
   token = os.getenv('CHATWORK_API_TOKEN')
   msg = f"[To:986396]徐雪蘭さん\n0517ノーマル検品指示書.xlsx は10MB超のためDriveリンクから取得お願いします:\nhttps://drive.google.com/file/d/{file_id}/view"
   requests.post(f'https://api.chatwork.com/v2/rooms/{room_id}/messages',
                 headers={'X-ChatWorkToken': token}, data={'body': msg}, timeout=10)
   ```

2. **Drive 上のファイル ID は MCP `mcp__claude_ai_Google_Drive__search_files` で取得**: `title = '0517ノーマル検品指示書.xlsx'` 等

3. (将来改修) `main.py batch-labels` の実装に「10MB超なら自動で Drive リンク fallback」を追加検討

## 空輸のときは `--air` を付ける (2026-09-09)

```bash
python3 main.py batch-labels --categories "ノーマル" --air
```

**プラン別名の末尾に「空輸」が付く**（`09/09ノーマル` → `09/09ノーマル空輸`）。
海上輸送か空輸かは後工程で効くのに、これまでシートのどこにも残っていなかった。
2026-09-04 は Chatwork の本文で伝えただけで、シートには痕跡がなかった。

後段の `/confirm-shipment` はプラン別名で対象を選ぶので、**空輸便は別名で分かれる**。
到着予定は既定が「出荷日の1ヶ月後」（海上前提）なので、空輸なら `--lead-days 14` で上書きする。

## 出した依頼を取り消す（`revert-shipment`, 2026-09-07 追加）

指示書を送ってしまった後に「やっぱり出さない」となったときは、手で消さずにこれを使う。

```bash
python3 main.py revert-shipment --alias "09/09ノーマル"                    # ドライラン（既定）
python3 main.py revert-shipment --alias "09/09ノーマル" --execute          # シートを巻き戻す
python3 main.py revert-shipment --alias "09/09ノーマル" --execute --delete-chatwork  # Chatworkの送付も取り下げる
```

| オプション | 既定 | 説明 |
|---|---|---|
| `--alias` | 必須 | 「プラン別名」で対象を選ぶ。**行番号では指定しない**（アーカイブで動くため） |
| `--execute` | 無し | 付けるまでドライラン。対象行を一覧表示するだけ |
| `--delete-chatwork` | 無し | 同じ依頼で送った本文・ラベル・指示書・検品指示書を削除する |
| `--since-hours` | 24 | Chatwork を遡る時間 |

### 何を消して何を残すか

**クリアするのは `梱包依頼日` `プラン別名` `納品プラン` の 3 列だけ。**
状態は数式なので書かない。`梱包依頼日` が空になれば `ifs` が自動で `梱包依頼必要` に戻る。

**購入数・SKU・FNSKU・在庫数・受領日には触れない。** 補完した SKU をやり直しのたびに失うのは無駄で、
2026-09-04 の誤ラベル事故のように SKU を直した直後に消すと修正がなかったことになる。

### Chatwork の取り下げ対象の決め方

**本文一致で消してはいけない。** 過去の投稿を巻き込む（実際に Chatwork の過去 5 件を誤削除した）。
`build_target_keywords` がプラン別名から 3 つの語を作り、**自分が `--since-hours` 以内に送った投稿**だけに絞る。

| 語 | 当てるもの |
|---|---|
| `梱包指示書` | 本文「【ノーマル】11件の梱包指示書を作成したので送付します。」 |
| `0909ノーマル` | `0909ノーマル指示書.xlsx` / `0909ノーマル検品指示書.xlsx` |
| `2026-09-09_ノーマル` | ラベル `2026-09-09_ノーマル.pdf` |

同じ日に送った**納品ラベル（`FBA…_納品ラベル.pdf`）は当たらない**ので消えない。
削除は不可逆なので、まずドライランで対象 ID を必ず確認すること。

### 試作納品プランは消えない

`納品プラン` 列を空にしても Amazon 側の試作プランは残る。実行後に URL を表示するので、
不要なら Seller Central で手動削除する（SP-API の `cancelInboundPlan` は未実装）。

## 再実行する場合の状態リセット

`/request-shipment` 実行後は「状態」列が「梱包依頼必要」→「梱包依頼済み」or「自宅発送」に更新され、再実行しても警告 (`納品分類「...」の行がありません`) で何も処理されない。再実行したい場合は、該当行の「状態」を一時的に「梱包依頼必要」に戻す:

```python
ws = repo.open_worksheet(cfg.sheet_id, cfg.purchase_sheet_name)
rows = [...]  # 対象行番号
batch = [{'range': f'N{r}', 'values': [['梱包依頼必要']]} for r in rows]  # N列=状態
ws.batch_update(batch, value_input_option='USER_ENTERED')
```

Chatwork 送信済みの取り下げが必要なら DELETE /v2/rooms/{room_id}/messages/{message_id}:

```python
import requests
ids = ['msgid1', ...]
for mid in ids:
    requests.delete(f'https://api.chatwork.com/v2/rooms/{ROOM_ID}/messages/{mid}',
                    headers={'X-ChatWorkToken': TOKEN}, timeout=10)
```
(Drive 上の生成済みファイルはそのまま残るので、Chatwork からの参照リンクだけが消える)

## 保存先

- ラベル: `.../8.指示書/ラベル/`
- 指示書: `.../8.指示書/検品指示書/`

## 注意事項

- .env と service_account.json が python/ ディレクトリに配置されている必要がある
- エラーが発生した場合は状況を報告する
- 実行結果のファイルパスをユーザに見やすく提示する
