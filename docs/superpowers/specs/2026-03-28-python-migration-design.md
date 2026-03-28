# Python移行設計書

## 概要

Google Apps Script（GAS）で実装された仕入管理・ラベル印刷自動化ツールをPythonに移行する。同一リポジトリ内に`python/`ディレクトリを作成し、GAS版を残しつつ段階的に移行する。

## 方針

- **アプローチ**: gspread + Google APIによる1:1移行（スプレッドシートをデータストアとして継続利用）
- **実行環境**: ローカルPC（CLIスクリプト）
- **UI**: GASダイアログ → CLI入力（click）

## GAS → Python 置き換えマッピング

| GAS API | Python置き換え | 用途 |
|---------|---------------|------|
| `SpreadsheetApp` | `gspread` | スプレッドシート操作 |
| `DriveApp` | `google-api-python-client` (Drive v3) | ファイルコピー・作成 |
| `UrlFetchApp` | `httpx` | HTTP通信（SP-API, Keepa等） |
| `PropertiesService` | `python-dotenv` (.env) | 環境変数 |
| `Utilities.formatDate()` | `datetime.strftime()` | 日付フォーマット |
| `Utilities.ungzip()` | `gzip` モジュール | GZIP展開 |
| `Browser.inputBox()` / `getUi().prompt()` | `click.prompt()` | ユーザー入力 |
| `HtmlService` (ダイアログ) | `click.Choice` | 選択UI |
| `CacheService` | メモリ内キャッシュ (dict) | 一時データ保持 |

## プロジェクト構造

```
python/
├── pyproject.toml
├── .env.example
├── src/
│   ├── domain/
│   │   ├── label/
│   │   │   ├── entities/
│   │   │   │   └── label_item.py        # LabelItem エンティティ
│   │   │   └── services/
│   │   │       └── label_aggregator.py   # SKU集計サービス
│   │   └── inspection/
│   │       ├── entities/
│   │       │   └── inspection_master_item.py
│   │       ├── repositories/
│   │       │   └── i_inspection_master_repository.py  # インターフェース
│   │       └── value_objects/
│   │           └── inspection_master_catalog.py
│   ├── infrastructure/
│   │   ├── amazon/
│   │   │   ├── auth.py                           # OAuth2トークン取得
│   │   │   ├── downloader.py                     # ラベルPDFダウンロード
│   │   │   ├── fnsku_getter.py                   # SKU→FNSKU取得
│   │   │   ├── inbound_plan_creator.py           # 納品プラン作成
│   │   │   └── merchant_listings_sku_resolver.py # ASIN→SKU解決
│   │   └── spreadsheet/
│   │       ├── base_sheet.py           # シート操作基底クラス
│   │       ├── base_row.py             # 行オブジェクト
│   │       ├── purchase_sheet.py       # 仕入管理シート
│   │       ├── home_shipment_sheet.py  # 自宅発送シート
│   │       ├── work_record_sheet.py    # 作業記録シート
│   │       ├── instruction_sheet.py    # 指示書作成
│   │       └── inspection_master_repo.py  # 検品マスタリポジトリ
│   ├── usecases/
│   │   ├── print_labels.py                        # ラベル+指示書生成
│   │   ├── inbound_plan.py                        # 納品プラン作成
│   │   ├── home_shipment.py                       # 自宅発送→納品プラン
│   │   ├── work_record.py                         # 作業記録
│   │   ├── create_inspection_sheet.py             # 検品シート作成
│   │   ├── update_status_estimate.py              # ステータス推測値更新
│   │   ├── update_inventory_estimate_from_stock.py # 在庫推測値更新
│   │   ├── split_row.py                           # 行分割
│   │   ├── update_arrival_date.py                 # 到着日更新
│   │   ├── set_filter.py                          # フィルタ設定
│   │   └── set_packing_info.py                    # 荷物情報入力
│   └── shared/
│       └── config.py                   # 環境設定・定数
├── tests/
│   ├── domain/
│   │   ├── label/
│   │   └── inspection/
│   ├── infrastructure/
│   │   ├── amazon/
│   │   └── spreadsheet/
│   └── usecases/
└── main.py                             # CLIエントリーポイント（click）
```

## 依存パッケージ

既存プロジェクト（auto-order, fullfilment等）に合わせてバージョンを統一:

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "management-helper"
version = "0.1.0"
description = "仕入管理・ラベル印刷自動化ツール"
requires-python = ">=3.12"

dependencies = [
    "gspread==6.1.2",
    "oauth2client==4.1.3",
    "google-api-python-client>=2.0",
    "httpx>=0.27",
    "python-dotenv==1.0.1",
    "click>=8.0",
    "tenacity>=8.0",
]

[project.optional-dependencies]
dev = [
    "pytest==8.3.3",
    "pytest-mock==3.14.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
python_classes = "Test*"
python_functions = "test_*"
addopts = "-v --tb=short"
pythonpath = ["src"]
```

## アーキテクチャ設計

### レイヤー構成（DDD）

```
main.py (CLI) → usecases → domain + infrastructure
```

- **domain層**: ビジネスロジック。外部依存なし。GAS版からほぼそのまま移植
- **infrastructure層**: 外部サービス連携。GAS APIをPythonライブラリに置き換え
- **usecases層**: アプリケーションロジック。domain層とinfrastructure層を組み合わせ
- **shared層**: 設定・定数管理

### BaseSheet / BaseRow パターン（Python版）

GAS版のBaseSheet/BaseRowパターンを維持する。gspreadのWorksheetをラップし、列名ベースのアクセスを提供。

```python
# BaseRow: 列名でアクセス可能な行オブジェクト
class BaseRow:
    def __init__(self, values: list[str], column_index_resolver: Callable[[str], int], row_number: int): ...
    def get(self, column_name: str) -> str: ...
    def __getitem__(self, index: int) -> str: ...

# BaseSheet: gspread.Worksheetのラッパー
class BaseSheet:
    def __init__(self, spreadsheet_id: str, sheet_name: str, header_row: int = 1): ...
    def get_all_row_data(self) -> list[BaseRow]: ...
    def get_rows_by_numbers(self, row_numbers: list[int]) -> list[BaseRow]: ...
    def write_cell(self, row_num: int, column_num: int, value: str) -> None: ...
    def write_column_by_func(self, column_name: str, value_func: Callable) -> None: ...
```

GAS版の`getActiveRowData()`（スプレッドシート上の選択範囲取得）はPython CLIでは使えない。代替として:
- 行番号を引数で受け取る `get_rows_by_numbers()`
- フィルタ条件で取得する `filter(column_name, values)`

### Amazon SP-API連携

GAS版と同じエンドポイント・ペイロード構造を維持。httpxで実装。

- **認証**: `auth.py`でOAuth2トークン取得（`httpx.post`）
- **ポーリング**: `tenacity`の`retry`デコレータで実装（レポート完了待機、納品プラン作成待機）
- **レート制限**: `time.sleep()`でインターバル制御

### Google認証

既存プロジェクト（auto-order, fullfilment）と同じ`oauth2client`パターンを採用:

```python
from oauth2client.service_account import ServiceAccountCredentials
import gspread

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
credentials = ServiceAccountCredentials.from_json_keyfile_name(
    credentials_file, scope
)
client = gspread.authorize(credentials)
```

### 設定管理（AppConfig）

既存プロジェクトと同じ`AppConfig` dataclassパターンを採用:

```python
@dataclass(frozen=True)
class AppConfig:
    credentials_file: str
    sheet_id: str
    purchase_sheet_name: str
    home_shipment_sheet_name: str
    work_record_sheet_name: str
    api_key: str
    api_secret: str
    refresh_token: str
    keepa_api_key: str
    # ...

    @classmethod
    def from_dotenv(cls, dotenv_path: str | None = None) -> "AppConfig":
        load_dotenv(dotenv_path=dotenv_path)
        return cls(
            credentials_file=os.getenv("GOOGLE_CREDENTIALS_FILE", "service_account.json"),
            sheet_id=os.getenv("SHEET_ID", ""),
            # ...
        )
```

### CLIエントリーポイント

clickでサブコマンドを定義:

```python
@click.group()
def cli(): ...

@cli.command()
@click.argument("row_numbers", nargs=-1, type=int)
def print_labels(row_numbers): ...

@cli.command()
@click.argument("row_numbers", nargs=-1, type=int)
def create_inbound_plan(row_numbers): ...

@cli.command()
@click.option("--type", type=click.Choice(["start", "end"]))
def work_record(type): ...

# ... 他のサブコマンド
```

### エラーハンドリング

- SP-APIエラー: httpxのHTTPStatusErrorをキャッチし、レスポンスボディを含めてログ出力
- gspreadエラー: APIExceptionをキャッチ
- ユーザー入力エラー: clickのバリデーションで制御

### ログ

CLAUDE.mdのログ管理ルールに従い、JSON構造化ログを出力。`logging`モジュール + カスタムJSONFormatterで実装。

## 移行対象ユースケース一覧

| # | ユースケース | GASファイル | Python関数 | 主要依存 |
|---|-------------|------------|-----------|---------|
| 1 | ラベル+指示書生成 | printLabels.js | `print_labels` | PurchaseSheet, Downloader, InstructionSheet, LabelAggregator |
| 2 | 納品プラン作成 | inboundPlan.js | `create_inbound_plan` | PurchaseSheet, InboundPlanCreator, WorkRecordSheet |
| 3 | 自宅発送→納品プラン | homeShipment.js | `create_inbound_plan_from_home` | HomeShipmentSheet, PurchaseSheet, InboundPlanCreator |
| 4 | 作業記録 | workRecord.js | `work_record` | WorkRecordSheet, PurchaseSheet |
| 5 | 不良品登録 | workRecord.js | `record_defect` | HomeShipmentSheet, PurchaseSheet, WorkRecordSheet |
| 6 | 検品シート作成 | createInspectionSheet.js | `create_inspection_sheet` | InspectionMasterRepo, DriveAPI |
| 7 | ステータス推測値更新 | updateStatusEstimate.js | `update_status_estimate` | PurchaseSheet, InboundPlanCreator |
| 8 | 在庫推測値更新 | updateInventoryEstimateFromStock.js | `update_inventory_estimate` | PurchaseSheet |
| 9 | 行分割 | splitRow.js | `split_row` | HomeShipmentSheet, PurchaseSheet |
| 10 | 到着日更新 | updateArrivalDate.js | `update_arrival_date` | HomeShipmentSheet, PurchaseSheet |
| 11 | フィルタ設定 | setfilter.js | `set_filter` | PurchaseSheet |
| 12 | 荷物情報入力 | setPackingInfo.js | `set_packing_info` | PurchaseSheet, InboundPlanCreator |

## GAS版の「選択範囲」問題

GAS版では`getActiveRowData()`でスプレッドシート上の選択行を取得していた。Python CLIでは代替手段が必要:

- **行番号指定**: CLIコマンドの引数で行番号を渡す
- **フィルタ条件**: ステータスや日付等でフィルタ（`update_status_estimate`等は元からフィルタベース）
- **対話的選択**: `click.prompt`で行を選択

各ユースケースで最適な方式を採用する。
