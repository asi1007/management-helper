---
description: /batch-labels コマンド - 梱包依頼必要の行を納品分類グループごとにラベル+指示書を一括作成し、Chatworkで送付
alwaysApply: true
---

# /batch-labels コマンド

ユーザが `/batch-labels` と入力した場合、以下を実行する。

## 事前確認: FC 分割 (自動化済み)

`/batch-labels` は実行時に各グループで SP-API 試作プランを作成し、`packingGroups` を取得して FC 分割を事前検知する。

### 自動的な動作

- **1 packingGroup (分割なし)**: 「納品プラン」列に試作プラン URL を `=HYPERLINK(...)` で書き込み、そのままラベル生成・指示書作成・Chatwork送信に進む。後段 `/update-fulfillment` でこの試作プランが再利用される。
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
4. **`/batch-labels --categories "元分類1,元分類2,..."` で全グループ再実行** (分割前グループを新分類名で置き換え、他グループは重複記載しても問題なし)
5. 古い試作プランは Seller Central で手動削除 (SP-API `cancelInboundPlan` は未実装)。次回 `/update-fulfillment` で新試作プランが自動再利用される

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
   - ラベルPDF分割: 合計15,000件超の場合、商品単位で10,000件以下ずつに分割
7. 梱包依頼日・プラン別名をシートに書き込み
8. 集計出力（重量×購入数、送料×購入数、関税×購入数）
9. Chatworkにグループごとにメッセージ+ファイルを送信（[To:986396]徐雪蘭さん宛）

## 自動検証 (実行時に常時、2026-05-19 強化)

`/batch-labels` は実行中に以下の検証を自動実行する。乖離があれば RuntimeError で停止し、ユーザー確認が促される。

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

batch-labels が終わったら、**必ず**指示書 xlsx の数量とラベル PDF のページ数が想定通りかを確認する。Amazon に送るラベル PDF は **1ページ=40ラベル** なので、合計数 / 40 (切り上げ) が期待ページ数。

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

- 数量と PDF ページが合わない → `InstructionSheet._extract_rows` のSKU集約と `Downloader` のラベル分割ロジック (15,000件超で分割など) を疑う
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

3. (将来改修) `batch-labels` 内に「10MB超なら自動で Drive リンク fallback」を追加検討

## 再実行する場合の状態リセット

batch-labels 実行後は「状態」列が「梱包依頼必要」→「梱包依頼済み」or「自宅発送」に更新され、再実行しても警告 (`納品分類「...」の行がありません`) で何も処理されない。再実行したい場合は、該当行の「状態」を一時的に「梱包依頼必要」に戻す:

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
