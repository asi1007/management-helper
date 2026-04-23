---
description: /batch-labels コマンド - 梱包依頼必要の行を納品分類グループごとにラベル+指示書を一括作成し、Chatworkで送付
alwaysApply: true
---

# /batch-labels コマンド

ユーザが `/batch-labels` と入力した場合、以下を実行する。

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
        title = str(r.get('商品名') or '').strip()[:50]
        qty = str(r.get('購入数') or '').strip()
        print(f'  行{r.row_number}: {title} | 数量:{qty}')
"
```

結果は以下の表形式で表示すること:

| グループ | 行 | 商品名 | 数量 |
|---------|-----|-------|------|
| **グループ名** (N行, 合計X個) | | | |
| | 行番号 | 商品名（短縮） | 数量 |

2. ユーザが処理するグループを選択したら、`--categories` オプションで指定して実行する:

```bash
cd /Users/wadaatsushi/Documents/automation/procurements/management-helper/python && python3 main.py batch-labels --categories "ノーマル,ファッション"
```

- `--categories` にカンマ区切りで納品分類名を指定
- 省略すると全グループ（自宅を除く）を処理

## 処理内容

1. 仕入管理シートから「状態」=「梱包依頼必要」の行を抽出
2. 「納品分類」でグループ化し、指定グループのみ処理
3. SKU空白チェック（空白があればエラー停止）
4. **自宅グループ**: 指示書xlsxのみ生成（ラベルPDF・検品指示書はスキップ）
5. **その他グループ**: ラベルPDF + 指示書xlsx + 検品指示書を生成（Google Drive共有フォルダに保存）
   - ラベルPDF分割: 合計15,000件超の場合、商品単位で10,000件以下ずつに分割
6. 梱包依頼日・プラン別名をシートに書き込み
7. 集計出力（重量×購入数、送料×購入数、関税×購入数）
8. Chatworkにグループごとにメッセージ+ファイルを送信（[To:986396]徐雪蘭さん宛）

## 保存先

- ラベル: `.../8.指示書/ラベル/`
- 指示書: `.../8.指示書/検品指示書/`

## 注意事項

- .env と service_account.json が python/ ディレクトリに配置されている必要がある
- エラーが発生した場合は状況を報告する
- 実行結果のファイルパスをユーザに見やすく提示する
