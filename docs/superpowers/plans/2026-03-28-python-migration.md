# Python移行 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** GASプロジェクトをPythonに1:1移行し、全12ユースケースをCLIから実行可能にする

**Architecture:** DDD 3層構造（domain / infrastructure / usecases）。gspread + oauth2client でスプレッドシート操作、httpx で SP-API/Keepa 連携、click で CLI。既存プロジェクト（auto-order, fullfilment）と同じパターンを採用。

**Tech Stack:** Python 3.12+, gspread 6.1.2, oauth2client 4.1.3, httpx, click, tenacity, python-dotenv, pytest

---

## ファイル構成

```
python/
├── pyproject.toml
├── .env.example
├── main.py                                          # CLIエントリーポイント
├── src/
│   ├── shared/
│   │   ├── config.py                                # AppConfig dataclass
│   │   └── logging.py                               # JsonFormatter
│   ├── domain/
│   │   ├── label/
│   │   │   ├── entities/label_item.py               # LabelItem
│   │   │   └── services/label_aggregator.py         # LabelAggregator
│   │   └── inspection/
│   │       ├── entities/inspection_master_item.py   # InspectionMasterItem
│   │       ├── repositories/i_inspection_master_repository.py
│   │       └── value_objects/inspection_master_catalog.py
│   ├── infrastructure/
│   │   ├── amazon/
│   │   │   ├── auth.py                              # SP-API OAuth2トークン取得
│   │   │   ├── downloader.py                        # ラベルPDFダウンロード
│   │   │   ├── fnsku_getter.py                      # SKU→FNSKU
│   │   │   ├── inbound_plan_creator.py              # 納品プラン作成
│   │   │   └── merchant_listings_sku_resolver.py    # ASIN→SKU
│   │   └── spreadsheet/
│   │       ├── base_sheets_repository.py            # gspread認証ラッパー
│   │       ├── base_row.py                          # BaseRow
│   │       ├── base_sheet.py                        # BaseSheet
│   │       ├── purchase_sheet.py                    # PurchaseSheet
│   │       ├── home_shipment_sheet.py               # HomeShipmentSheet
│   │       ├── work_record_sheet.py                 # WorkRecordSheet
│   │       ├── instruction_sheet.py                 # InstructionSheet
│   │       └── inspection_master_repo.py            # InspectionMasterRepo
│   └── usecases/
│       ├── print_labels.py
│       ├── inbound_plan.py
│       ├── home_shipment.py
│       ├── work_record.py
│       ├── create_inspection_sheet.py
│       ├── update_status_estimate.py
│       ├── update_inventory_estimate_from_stock.py
│       ├── split_row.py
│       ├── update_arrival_date.py
│       ├── set_filter.py
│       └── set_packing_info.py
└── tests/
    ├── conftest.py
    ├── domain/
    │   ├── label/
    │   │   ├── test_label_item.py
    │   │   └── test_label_aggregator.py
    │   └── inspection/
    │       └── test_inspection_master_catalog.py
    ├── infrastructure/
    │   ├── amazon/
    │   │   ├── test_auth.py
    │   │   ├── test_downloader.py
    │   │   ├── test_fnsku_getter.py
    │   │   └── test_merchant_listings_sku_resolver.py
    │   └── spreadsheet/
    │       ├── test_base_row.py
    │       ├── test_base_sheet.py
    │       └── test_purchase_sheet.py
    └── usecases/
        ├── test_work_record.py
        └── test_print_labels.py
```

---

## Task 1: プロジェクト骨格

**Files:**
- Create: `python/pyproject.toml`
- Create: `python/.env.example`
- Create: `python/src/shared/__init__.py` (空)
- Create: `python/src/domain/__init__.py` (空)
- Create: `python/src/infrastructure/__init__.py` (空)
- Create: `python/src/usecases/__init__.py` (空)
- Create: `python/tests/__init__.py` (空)

- [ ] **Step 1: ディレクトリ構造を作成**

```bash
cd /Users/wadaatsushi/Documents/automation/procurements/management-helper
mkdir -p python/src/{shared,domain/label/entities,domain/label/services,domain/inspection/entities,domain/inspection/repositories,domain/inspection/value_objects,infrastructure/amazon,infrastructure/spreadsheet,usecases}
mkdir -p python/tests/{domain/label,domain/inspection,infrastructure/amazon,infrastructure/spreadsheet,usecases}
```

- [ ] **Step 2: pyproject.toml を作成**

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "management-helper"
version = "0.1.0"
description = "仕入管理・ラベル印刷自動化ツール"
requires-python = ">=3.12"
license = {text = "MIT"}

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

- [ ] **Step 3: .env.example を作成**

```env
GOOGLE_CREDENTIALS_FILE=service_account.json
SHEET_ID=YOUR_SHEET_ID_HERE
PURCHASE_SHEET_NAME=仕入管理
HOME_SHIPMENT_SHEET_NAME=自宅発送
WORK_RECORD_SHEET_NAME=作業記録
INSTRUCTION_SHEET_NAME=yiwu指示書
INSPECTION_MASTER_SHEET_ID=YOUR_INSPECTION_MASTER_SHEET_ID
INSPECTION_MASTER_SHEET_GID=YOUR_INSPECTION_MASTER_SHEET_GID
INSPECTION_TEMPLATE_SHEET_ID=YOUR_INSPECTION_TEMPLATE_SHEET_ID
INSPECTION_TEMPLATE_SHEET_GID=YOUR_INSPECTION_TEMPLATE_SHEET_GID
API_KEY=YOUR_SP_API_KEY
API_SECRET=YOUR_SP_API_SECRET
REFRESH_TOKEN=YOUR_SP_API_REFRESH_TOKEN
KEEPA_API_KEY=YOUR_KEEPA_API_KEY
```

- [ ] **Step 4: __init__.py を全ディレクトリに作成**

すべてのパッケージディレクトリに空の `__init__.py` を作成:

```bash
find python/src python/tests -type d -exec touch {}/__init__.py \;
```

- [ ] **Step 5: 依存パッケージをインストール**

```bash
cd python && pip install -e ".[dev]"
```

- [ ] **Step 6: pytest が動作することを確認**

```bash
cd python && pytest --co -q
```

Expected: `no tests ran` (テストファイルがまだないため)

- [ ] **Step 7: コミット**

```bash
git add python/
git commit -m "feat: Python版プロジェクト骨格を作成"
```

---

## Task 2: shared層 (AppConfig + JsonFormatter)

**Files:**
- Create: `python/src/shared/config.py`
- Create: `python/src/shared/logging.py`
- Test: `python/tests/test_config.py`

- [ ] **Step 1: config のテストを書く**

```python
# python/tests/test_config.py
import os
import pytest
from shared.config import AppConfig


class TestAppConfig:
    def test_from_env_reads_all_fields(self, monkeypatch, tmp_path):
        creds = tmp_path / "creds.json"
        creds.write_text("{}", encoding="utf-8")

        monkeypatch.setenv("GOOGLE_CREDENTIALS_FILE", str(creds))
        monkeypatch.setenv("SHEET_ID", "test-sheet-id")
        monkeypatch.setenv("PURCHASE_SHEET_NAME", "仕入管理")
        monkeypatch.setenv("HOME_SHIPMENT_SHEET_NAME", "自宅発送")
        monkeypatch.setenv("WORK_RECORD_SHEET_NAME", "作業記録")
        monkeypatch.setenv("INSTRUCTION_SHEET_NAME", "yiwu指示書")
        monkeypatch.setenv("INSPECTION_MASTER_SHEET_ID", "master-id")
        monkeypatch.setenv("INSPECTION_MASTER_SHEET_GID", "414729247")
        monkeypatch.setenv("INSPECTION_TEMPLATE_SHEET_ID", "template-id")
        monkeypatch.setenv("INSPECTION_TEMPLATE_SHEET_GID", "1711200534")
        monkeypatch.setenv("API_KEY", "test-api-key")
        monkeypatch.setenv("API_SECRET", "test-api-secret")
        monkeypatch.setenv("REFRESH_TOKEN", "test-refresh-token")
        monkeypatch.setenv("KEEPA_API_KEY", "test-keepa-key")

        config = AppConfig.from_env()

        assert config.credentials_file == str(creds)
        assert config.sheet_id == "test-sheet-id"
        assert config.purchase_sheet_name == "仕入管理"
        assert config.api_key == "test-api-key"
        assert config.keepa_api_key == "test-keepa-key"

    def test_from_env_uses_defaults(self, monkeypatch):
        monkeypatch.delenv("SHEET_ID", raising=False)
        monkeypatch.delenv("PURCHASE_SHEET_NAME", raising=False)

        config = AppConfig.from_env()

        assert config.sheet_id == ""
        assert config.purchase_sheet_name == "仕入管理"
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
cd python && pytest tests/test_config.py -v
```

Expected: FAIL (`ModuleNotFoundError: No module named 'shared.config'`)

- [ ] **Step 3: config.py を実装**

```python
# python/src/shared/config.py
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

DEFAULT_MARKETPLACE_ID = "A1VC38T7YXB528"

SHIP_FROM_ADDRESS = {
    "name": "和田篤",
    "companyName": "",
    "addressLine1": "久喜本847-14",
    "addressLine2": "",
    "city": "久喜市",
    "stateOrProvinceCode": "埼玉県",
    "postalCode": "3460031",
    "countryCode": "JP",
    "phoneNumber": "05035540337",
    "email": "",
}


@dataclass(frozen=True)
class AppConfig:
    credentials_file: str
    sheet_id: str
    purchase_sheet_name: str
    home_shipment_sheet_name: str
    work_record_sheet_name: str
    instruction_sheet_name: str
    inspection_master_sheet_id: str
    inspection_master_sheet_gid: str
    inspection_template_sheet_id: str
    inspection_template_sheet_gid: str
    api_key: str
    api_secret: str
    refresh_token: str
    keepa_api_key: str

    @classmethod
    def from_env(cls) -> AppConfig:
        return cls(
            credentials_file=os.getenv("GOOGLE_CREDENTIALS_FILE", "service_account.json"),
            sheet_id=os.getenv("SHEET_ID", ""),
            purchase_sheet_name=os.getenv("PURCHASE_SHEET_NAME", "仕入管理"),
            home_shipment_sheet_name=os.getenv("HOME_SHIPMENT_SHEET_NAME", "自宅発送"),
            work_record_sheet_name=os.getenv("WORK_RECORD_SHEET_NAME", "作業記録"),
            instruction_sheet_name=os.getenv("INSTRUCTION_SHEET_NAME", "yiwu指示書"),
            inspection_master_sheet_id=os.getenv("INSPECTION_MASTER_SHEET_ID", ""),
            inspection_master_sheet_gid=os.getenv("INSPECTION_MASTER_SHEET_GID", ""),
            inspection_template_sheet_id=os.getenv("INSPECTION_TEMPLATE_SHEET_ID", ""),
            inspection_template_sheet_gid=os.getenv("INSPECTION_TEMPLATE_SHEET_GID", ""),
            api_key=os.getenv("API_KEY", ""),
            api_secret=os.getenv("API_SECRET", ""),
            refresh_token=os.getenv("REFRESH_TOKEN", ""),
            keepa_api_key=os.getenv("KEEPA_API_KEY", ""),
        )

    @classmethod
    def from_dotenv(cls, *, dotenv_path: str | None = None) -> AppConfig:
        load_dotenv(dotenv_path=dotenv_path)
        return cls.from_env()
```

- [ ] **Step 4: テストが通ることを確認**

```bash
cd python && pytest tests/test_config.py -v
```

Expected: 2 passed

- [ ] **Step 5: logging.py を実装**

```python
# python/src/shared/logging.py
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path


class JsonFormatter(logging.Formatter):
    def __init__(self, version: str) -> None:
        super().__init__()
        self._version = version

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "version": self._version,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def get_version() -> str:
    toml_path = Path(__file__).resolve().parent.parent.parent / "pyproject.toml"
    try:
        import tomllib
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)
        return data["project"]["version"]
    except Exception:
        return "unknown"


def setup_logging() -> None:
    version = get_version()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(version))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
```

- [ ] **Step 6: コミット**

```bash
git add python/src/shared/ python/tests/test_config.py
git commit -m "feat: AppConfigとJsonFormatterを実装"
```

---

## Task 3: domain層 - label ドメイン

**Files:**
- Create: `python/src/domain/label/entities/label_item.py`
- Create: `python/src/domain/label/services/label_aggregator.py`
- Test: `python/tests/domain/label/test_label_item.py`
- Test: `python/tests/domain/label/test_label_aggregator.py`

- [ ] **Step 1: LabelItem のテストを書く**

```python
# python/tests/domain/label/test_label_item.py
import pytest
from domain.label.entities.label_item import LabelItem


class TestLabelItem:
    def test_valid_creation(self):
        item = LabelItem(sku="TEST-SKU", quantity=10)
        assert item.sku == "TEST-SKU"
        assert item.quantity == 10

    def test_trims_sku(self):
        item = LabelItem(sku="  TEST-SKU  ", quantity=5)
        assert item.sku == "TEST-SKU"

    def test_empty_sku_raises(self):
        with pytest.raises(ValueError, match="SKUが空です"):
            LabelItem(sku="", quantity=10)

    def test_zero_quantity_raises(self):
        with pytest.raises(ValueError, match="数量が不正です"):
            LabelItem(sku="SKU", quantity=0)

    def test_negative_quantity_raises(self):
        with pytest.raises(ValueError, match="数量が不正です"):
            LabelItem(sku="SKU", quantity=-1)

    def test_to_msku_quantity(self):
        item = LabelItem(sku="SKU-001", quantity=5)
        assert item.to_msku_quantity() == {"msku": "SKU-001", "quantity": 5}
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
cd python && pytest tests/domain/label/test_label_item.py -v
```

Expected: FAIL

- [ ] **Step 3: LabelItem を実装**

```python
# python/src/domain/label/entities/label_item.py
from __future__ import annotations


class LabelItem:
    def __init__(self, sku: str, quantity: int) -> None:
        self.sku = str(sku or "").strip()
        self.quantity = int(quantity) if quantity else 0

        if not self.sku:
            raise ValueError("SKUが空です")
        if self.quantity <= 0:
            raise ValueError(f"数量が不正です: {quantity}")

    def to_msku_quantity(self) -> dict[str, str | int]:
        return {"msku": self.sku, "quantity": self.quantity}
```

- [ ] **Step 4: LabelItem テストが通ることを確認**

```bash
cd python && pytest tests/domain/label/test_label_item.py -v
```

Expected: 6 passed

- [ ] **Step 5: LabelAggregator のテストを書く**

```python
# python/tests/domain/label/test_label_aggregator.py
import pytest
from domain.label.services.label_aggregator import LabelAggregator
from domain.label.entities.label_item import LabelItem


class FakeRow:
    def __init__(self, data: dict[str, str]):
        self._data = data

    def get(self, column_name: str) -> str:
        return self._data.get(column_name, "")


class TestLabelAggregator:
    def test_aggregate_single_sku(self):
        rows = [FakeRow({"SKU": "SKU-1", "購入数": "10"})]
        items = LabelAggregator().aggregate(rows)
        assert len(items) == 1
        assert items[0].sku == "SKU-1"
        assert items[0].quantity == 10

    def test_aggregate_merges_same_sku(self):
        rows = [
            FakeRow({"SKU": "SKU-1", "購入数": "10"}),
            FakeRow({"SKU": "SKU-1", "購入数": "5"}),
        ]
        items = LabelAggregator().aggregate(rows)
        assert len(items) == 1
        assert items[0].quantity == 15

    def test_aggregate_multiple_skus(self):
        rows = [
            FakeRow({"SKU": "SKU-1", "購入数": "10"}),
            FakeRow({"SKU": "SKU-2", "購入数": "20"}),
        ]
        items = LabelAggregator().aggregate(rows)
        assert len(items) == 2

    def test_aggregate_skips_empty_sku(self):
        rows = [
            FakeRow({"SKU": "", "購入数": "10"}),
            FakeRow({"SKU": "SKU-1", "購入数": "5"}),
        ]
        items = LabelAggregator().aggregate(rows)
        assert len(items) == 1

    def test_aggregate_no_valid_skus_raises(self):
        rows = [FakeRow({"SKU": "", "購入数": "0"})]
        with pytest.raises(ValueError, match="有効なSKUがありません"):
            LabelAggregator().aggregate(rows)

    def test_aggregate_empty_rows_raises(self):
        with pytest.raises(ValueError, match="有効なSKUがありません"):
            LabelAggregator().aggregate([])
```

- [ ] **Step 6: テストが失敗することを確認**

```bash
cd python && pytest tests/domain/label/test_label_aggregator.py -v
```

Expected: FAIL

- [ ] **Step 7: LabelAggregator を実装**

```python
# python/src/domain/label/services/label_aggregator.py
from __future__ import annotations

from typing import Protocol

from domain.label.entities.label_item import LabelItem


class RowLike(Protocol):
    def get(self, column_name: str) -> str: ...


class LabelAggregator:
    def aggregate(self, rows: list[RowLike]) -> list[LabelItem]:
        sku_totals: dict[str, int] = {}

        for row in rows or []:
            sku = str(row.get("SKU") or "").strip()
            quantity = int(row.get("購入数") or 0) if row.get("購入数") else 0

            if not sku or quantity <= 0:
                continue
            sku_totals[sku] = sku_totals.get(sku, 0) + quantity

        items = [LabelItem(sku=sku, quantity=qty) for sku, qty in sku_totals.items()]
        if not items:
            raise ValueError("有効なSKUがありません")
        return items
```

- [ ] **Step 8: テストが通ることを確認**

```bash
cd python && pytest tests/domain/label/ -v
```

Expected: 12 passed

- [ ] **Step 9: コミット**

```bash
git add python/src/domain/label/ python/tests/domain/label/
git commit -m "feat: LabelItem, LabelAggregatorを実装"
```

---

## Task 4: domain層 - inspection ドメイン

**Files:**
- Create: `python/src/domain/inspection/entities/inspection_master_item.py`
- Create: `python/src/domain/inspection/repositories/i_inspection_master_repository.py`
- Create: `python/src/domain/inspection/value_objects/inspection_master_catalog.py`
- Test: `python/tests/domain/inspection/test_inspection_master_catalog.py`

- [ ] **Step 1: InspectionMasterCatalog のテストを書く**

```python
# python/tests/domain/inspection/test_inspection_master_catalog.py
import pytest
from domain.inspection.entities.inspection_master_item import InspectionMasterItem
from domain.inspection.value_objects.inspection_master_catalog import InspectionMasterCatalog


class TestInspectionMasterCatalog:
    def _make_catalog(self) -> InspectionMasterCatalog:
        items = {
            "B001": InspectionMasterItem(
                asin="B001", product_name="商品A",
                inspection_point="傷チェック", detail_instruction_url="https://example.com/a",
            ),
            "B002": InspectionMasterItem(
                asin="B002", product_name="商品B",
                inspection_point="動作確認", detail_instruction_url="",
            ),
        }
        return InspectionMasterCatalog(items_by_asin=items)

    def test_has_existing_asin(self):
        catalog = self._make_catalog()
        assert catalog.has("B001") is True

    def test_has_missing_asin(self):
        catalog = self._make_catalog()
        assert catalog.has("B999") is False

    def test_get_returns_item(self):
        catalog = self._make_catalog()
        item = catalog.get("B001")
        assert item is not None
        assert item.product_name == "商品A"

    def test_get_returns_none_for_missing(self):
        catalog = self._make_catalog()
        assert catalog.get("B999") is None

    def test_filter_by_asins(self):
        catalog = self._make_catalog()
        filtered = catalog.filter_by_asins(["B001"])
        assert filtered.size() == 1
        assert filtered.has("B001")
        assert not filtered.has("B002")

    def test_size(self):
        catalog = self._make_catalog()
        assert catalog.size() == 2

    def test_asins(self):
        catalog = self._make_catalog()
        assert sorted(catalog.asins()) == ["B001", "B002"]
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
cd python && pytest tests/domain/inspection/test_inspection_master_catalog.py -v
```

Expected: FAIL

- [ ] **Step 3: InspectionMasterItem を実装**

```python
# python/src/domain/inspection/entities/inspection_master_item.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InspectionMasterItem:
    asin: str
    product_name: str
    inspection_point: str
    detail_instruction_url: str
```

- [ ] **Step 4: IInspectionMasterRepository を実装**

```python
# python/src/domain/inspection/repositories/i_inspection_master_repository.py
from __future__ import annotations

from typing import Protocol

from domain.inspection.value_objects.inspection_master_catalog import InspectionMasterCatalog


class IInspectionMasterRepository(Protocol):
    def load(self) -> InspectionMasterCatalog: ...
```

- [ ] **Step 5: InspectionMasterCatalog を実装**

```python
# python/src/domain/inspection/value_objects/inspection_master_catalog.py
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from domain.inspection.entities.inspection_master_item import InspectionMasterItem


class InspectionMasterCatalog:
    def __init__(self, items_by_asin: dict[str, InspectionMasterItem]) -> None:
        self._items_by_asin = dict(items_by_asin)

    def filter_by_asins(self, asins: list[str]) -> InspectionMasterCatalog:
        asin_set = set(asins)
        filtered = {k: v for k, v in self._items_by_asin.items() if k in asin_set}
        return InspectionMasterCatalog(items_by_asin=filtered)

    def has(self, asin: str) -> bool:
        return asin in self._items_by_asin

    def get(self, asin: str) -> InspectionMasterItem | None:
        return self._items_by_asin.get(asin)

    def size(self) -> int:
        return len(self._items_by_asin)

    def asins(self) -> list[str]:
        return list(self._items_by_asin.keys())
```

- [ ] **Step 6: テストが通ることを確認**

```bash
cd python && pytest tests/domain/inspection/ -v
```

Expected: 7 passed

- [ ] **Step 7: コミット**

```bash
git add python/src/domain/inspection/ python/tests/domain/inspection/
git commit -m "feat: inspectionドメイン(InspectionMasterItem, Catalog, Repository IF)を実装"
```

---

## Task 5: infrastructure層 - スプレッドシート基盤 (BaseSheetsRepository, BaseRow, BaseSheet)

**Files:**
- Create: `python/src/infrastructure/spreadsheet/base_sheets_repository.py`
- Create: `python/src/infrastructure/spreadsheet/base_row.py`
- Create: `python/src/infrastructure/spreadsheet/base_sheet.py`
- Test: `python/tests/infrastructure/spreadsheet/test_base_row.py`
- Test: `python/tests/infrastructure/spreadsheet/test_base_sheet.py`

- [ ] **Step 1: BaseRow のテストを書く**

```python
# python/tests/infrastructure/spreadsheet/test_base_row.py
import pytest
from infrastructure.spreadsheet.base_row import BaseRow


class TestBaseRow:
    def _make_resolver(self, headers: list[str]):
        index_map = {h.strip(): i for i, h in enumerate(headers) if h.strip()}
        def resolver(name: str) -> int:
            key = name.strip()
            if key not in index_map:
                raise ValueError(f'列 "{key}" が見つかりません')
            return index_map[key]
        return resolver

    def test_get_by_column_name(self):
        resolver = self._make_resolver(["ASIN", "SKU", "購入数"])
        row = BaseRow(values=["B001", "SKU-1", "10"], column_index_resolver=resolver, row_number=5)
        assert row.get("ASIN") == "B001"
        assert row.get("SKU") == "SKU-1"
        assert row.get("購入数") == "10"

    def test_get_trims_string_values(self):
        resolver = self._make_resolver(["name"])
        row = BaseRow(values=["  hello  "], column_index_resolver=resolver, row_number=1)
        assert row.get("name") == "hello"

    def test_getitem_by_index(self):
        resolver = self._make_resolver(["A", "B"])
        row = BaseRow(values=["x", "y"], column_index_resolver=resolver, row_number=1)
        assert row[0] == "x"
        assert row[1] == "y"

    def test_row_number(self):
        resolver = self._make_resolver(["A"])
        row = BaseRow(values=["v"], column_index_resolver=resolver, row_number=42)
        assert row.row_number == 42

    def test_get_unknown_column_raises(self):
        resolver = self._make_resolver(["A"])
        row = BaseRow(values=["v"], column_index_resolver=resolver, row_number=1)
        with pytest.raises(ValueError, match="見つかりません"):
            row.get("unknown")

    def test_get_non_string_returns_as_is(self):
        resolver = self._make_resolver(["num"])
        row = BaseRow(values=[42], column_index_resolver=resolver, row_number=1)
        assert row.get("num") == 42
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
cd python && pytest tests/infrastructure/spreadsheet/test_base_row.py -v
```

Expected: FAIL

- [ ] **Step 3: BaseRow を実装**

```python
# python/src/infrastructure/spreadsheet/base_row.py
from __future__ import annotations

from typing import Any, Callable


class BaseRow:
    def __init__(
        self,
        values: list[Any],
        column_index_resolver: Callable[[str], int],
        row_number: int,
    ) -> None:
        self._values = list(values)
        self._column_index_resolver = column_index_resolver
        self.row_number = row_number

    def get(self, column_name: str) -> Any:
        idx = self._column_index_resolver(column_name)
        v = self._values[idx]
        return v.strip() if isinstance(v, str) else v

    def __getitem__(self, index: int) -> Any:
        return self._values[index]

    def __setitem__(self, index: int, value: Any) -> None:
        self._values[index] = value

    def __len__(self) -> int:
        return len(self._values)
```

- [ ] **Step 4: BaseRow テストが通ることを確認**

```bash
cd python && pytest tests/infrastructure/spreadsheet/test_base_row.py -v
```

Expected: 6 passed

- [ ] **Step 5: BaseSheetsRepository を実装**

```python
# python/src/infrastructure/spreadsheet/base_sheets_repository.py
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

import gspread
from oauth2client.service_account import ServiceAccountCredentials

if TYPE_CHECKING:
    from gspread import Client, Spreadsheet, Worksheet


class BaseSheetsRepository:
    def __init__(self, credentials_file: str, client: Optional[Client] = None) -> None:
        self.credentials_file = credentials_file
        self.client: Client = client if client is not None else self._authenticate()

    def _authenticate(self) -> Client:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        try:
            credentials = ServiceAccountCredentials.from_json_keyfile_name(
                self.credentials_file, scope
            )
            return gspread.authorize(credentials)
        except Exception as e:
            raise RuntimeError(f"Google Sheets APIの認証に失敗しました: {e}") from e

    def open_spreadsheet(self, sheet_id: str) -> Spreadsheet:
        return self.client.open_by_key(sheet_id)

    def open_worksheet(self, sheet_id: str, sheet_name: str) -> Worksheet:
        spreadsheet = self.open_spreadsheet(sheet_id)
        return spreadsheet.worksheet(sheet_name)
```

- [ ] **Step 6: BaseSheet を実装**

```python
# python/src/infrastructure/spreadsheet/base_sheet.py
from __future__ import annotations

import logging
from typing import Any, Callable, TYPE_CHECKING

from infrastructure.spreadsheet.base_row import BaseRow
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository

if TYPE_CHECKING:
    from gspread import Worksheet

logger = logging.getLogger(__name__)


class BaseSheet:
    def __init__(
        self,
        repo: BaseSheetsRepository,
        sheet_id: str,
        sheet_name: str,
        header_row: int = 1,
    ) -> None:
        self._repo = repo
        self._worksheet: Worksheet = repo.open_worksheet(sheet_id, sheet_name)
        self.header_row = header_row
        self.start_row = header_row + 1

        all_values = self._worksheet.get_all_values()
        if len(all_values) < header_row:
            raise ValueError(f'シート "{sheet_name}" にヘッダー行({header_row})がありません')

        header_raw = all_values[header_row - 1]
        self._headers: list[str] = [str(h).strip() for h in header_raw]
        self._header_index_map: dict[str, int] = {}
        for i, key in enumerate(self._headers):
            if key and key not in self._header_index_map:
                self._header_index_map[key] = i

        data_rows = all_values[header_row:]
        self.all_data: list[BaseRow] = [
            BaseRow(
                values=row,
                column_index_resolver=self._get_column_index_by_name,
                row_number=self.start_row + i,
            )
            for i, row in enumerate(data_rows)
        ]
        self.data: list[BaseRow] = list(self.all_data)

    def _get_column_index_by_name(self, column_name: str) -> int:
        key = str(column_name).strip()
        idx = self._header_index_map.get(key)
        if idx is not None:
            return idx
        valid = [h for h in self._headers if h]
        raise ValueError(f'列 "{key}" が見つかりません。ヘッダー: {valid}')

    def get_rows_by_numbers(self, row_numbers: list[int]) -> list[BaseRow]:
        row_set = set(row_numbers)
        rows = [r for r in self.all_data if r.row_number in row_set]
        self.data = rows
        return rows

    def filter(self, column_name: str, values: list[Any]) -> list[BaseRow]:
        col_idx = self._get_column_index_by_name(column_name)
        str_values = {str(v) for v in values}
        filtered = [r for r in self.all_data if str(r[col_idx]) in str_values]
        self.data = filtered
        logger.info("%sでフィルタリング: %d行が見つかりました", column_name, len(filtered))
        return filtered

    def write_cell(self, row_num: int, column_num: int, value: Any) -> None:
        self._worksheet.update_cell(row_num, column_num, value)
        logger.info("%d行目の%d列に書き込みました", row_num, column_num)

    def write_formula(self, row_num: int, column_num: int, formula: str) -> None:
        cell_label = gspread.utils.rowcol_to_a1(row_num, column_num)
        self._worksheet.update_acell(cell_label, formula)
        logger.info("%d行目の%d列に数式を書き込みました", row_num, column_num)

    def write_column_by_func(
        self, column_name: str, value_func: Callable[[BaseRow, int], Any | None]
    ) -> int:
        col_num = self._get_column_index_by_name(column_name) + 1
        count = 0
        for i, row in enumerate(self.data):
            value = value_func(row, i)
            if value is None:
                continue
            if isinstance(value, dict) and value.get("type") == "formula":
                self.write_formula(row.row_number, col_num, value["value"])
            else:
                self.write_cell(row.row_number, col_num, value)
            count += 1
        logger.info("%sを%d行に書き込みました", column_name, count)
        return count
```

- [ ] **Step 7: BaseSheet のテストを書く**

```python
# python/tests/infrastructure/spreadsheet/test_base_sheet.py
from unittest.mock import MagicMock
import pytest
from infrastructure.spreadsheet.base_row import BaseRow
from infrastructure.spreadsheet.base_sheet import BaseSheet


class TestBaseSheet:
    def _make_sheet(self, all_values: list[list[str]], header_row: int = 1) -> BaseSheet:
        mock_worksheet = MagicMock()
        mock_worksheet.get_all_values.return_value = all_values

        mock_repo = MagicMock()
        mock_repo.open_worksheet.return_value = mock_worksheet

        sheet = BaseSheet(
            repo=mock_repo,
            sheet_id="test-id",
            sheet_name="test-sheet",
            header_row=header_row,
        )
        return sheet

    def test_loads_data_rows(self):
        all_values = [
            ["ASIN", "SKU", "購入数"],
            ["B001", "SKU-1", "10"],
            ["B002", "SKU-2", "20"],
        ]
        sheet = self._make_sheet(all_values)
        assert len(sheet.data) == 2
        assert sheet.data[0].get("ASIN") == "B001"
        assert sheet.data[1].get("購入数") == "20"

    def test_row_numbers_start_after_header(self):
        all_values = [
            ["A"],
            ["v1"],
            ["v2"],
        ]
        sheet = self._make_sheet(all_values)
        assert sheet.data[0].row_number == 2
        assert sheet.data[1].row_number == 3

    def test_header_row_4(self):
        all_values = [
            ["x"], ["x"], ["x"],
            ["ASIN", "SKU"],
            ["B001", "SKU-1"],
        ]
        sheet = self._make_sheet(all_values, header_row=4)
        assert len(sheet.data) == 1
        assert sheet.data[0].get("ASIN") == "B001"
        assert sheet.data[0].row_number == 5

    def test_get_rows_by_numbers(self):
        all_values = [
            ["A"],
            ["v1"],
            ["v2"],
            ["v3"],
        ]
        sheet = self._make_sheet(all_values)
        rows = sheet.get_rows_by_numbers([2, 4])
        assert len(rows) == 2
        assert rows[0].row_number == 2
        assert rows[1].row_number == 4

    def test_filter(self):
        all_values = [
            ["status", "name"],
            ["active", "a"],
            ["inactive", "b"],
            ["active", "c"],
        ]
        sheet = self._make_sheet(all_values)
        rows = sheet.filter("status", ["active"])
        assert len(rows) == 2
        assert rows[0].get("name") == "a"
        assert rows[1].get("name") == "c"

    def test_unknown_column_raises(self):
        all_values = [["A"], ["v"]]
        sheet = self._make_sheet(all_values)
        with pytest.raises(ValueError, match="見つかりません"):
            sheet.filter("unknown", ["x"])
```

- [ ] **Step 8: テストが通ることを確認**

```bash
cd python && pytest tests/infrastructure/spreadsheet/ -v
```

Expected: 12 passed

- [ ] **Step 9: コミット**

```bash
git add python/src/infrastructure/spreadsheet/base_sheets_repository.py python/src/infrastructure/spreadsheet/base_row.py python/src/infrastructure/spreadsheet/base_sheet.py python/tests/infrastructure/spreadsheet/
git commit -m "feat: スプレッドシート基盤(BaseSheetsRepository, BaseRow, BaseSheet)を実装"
```

---

## Task 6: infrastructure層 - Amazon SP-API認証 + Downloader

**Files:**
- Create: `python/src/infrastructure/amazon/auth.py`
- Create: `python/src/infrastructure/amazon/downloader.py`
- Test: `python/tests/infrastructure/amazon/test_auth.py`
- Test: `python/tests/infrastructure/amazon/test_downloader.py`

- [ ] **Step 1: auth のテストを書く**

```python
# python/tests/infrastructure/amazon/test_auth.py
import pytest
from unittest.mock import patch, MagicMock
from infrastructure.amazon.auth import get_auth_token


class TestGetAuthToken:
    def test_returns_access_token(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "test-token-123"}
        mock_response.raise_for_status = MagicMock()

        with patch("infrastructure.amazon.auth.httpx.post", return_value=mock_response):
            token = get_auth_token(
                api_key="key", api_secret="secret", refresh_token="refresh"
            )
        assert token == "test-token-123"

    def test_raises_on_missing_token(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        with patch("infrastructure.amazon.auth.httpx.post", return_value=mock_response):
            with pytest.raises(KeyError):
                get_auth_token(
                    api_key="key", api_secret="secret", refresh_token="refresh"
                )
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
cd python && pytest tests/infrastructure/amazon/test_auth.py -v
```

Expected: FAIL

- [ ] **Step 3: auth.py を実装**

```python
# python/src/infrastructure/amazon/auth.py
from __future__ import annotations

import httpx


def get_auth_token(api_key: str, api_secret: str, refresh_token: str) -> str:
    url = "https://api.amazon.com/auth/o2/token"
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": api_key,
        "client_secret": api_secret,
    }
    response = httpx.post(url, data=payload)
    response.raise_for_status()
    return response.json()["access_token"]
```

- [ ] **Step 4: auth テストが通ることを確認**

```bash
cd python && pytest tests/infrastructure/amazon/test_auth.py -v
```

Expected: 2 passed

- [ ] **Step 5: Downloader のテストを書く**

```python
# python/tests/infrastructure/amazon/test_downloader.py
import pytest
from infrastructure.amazon.downloader import Downloader


class TestSplitByQuantityLimit:
    def test_no_split_when_under_limit(self):
        dl = Downloader(auth_token="dummy", drive_service=None)
        items = [{"msku": "A", "quantity": 100}]
        chunks = dl._split_by_quantity_limit(items)
        assert len(chunks) == 1
        assert chunks[0] == items

    def test_splits_when_over_15000(self):
        dl = Downloader(auth_token="dummy", drive_service=None)
        items = [{"msku": "A", "quantity": 16000}]
        chunks = dl._split_by_quantity_limit(items)
        assert len(chunks) > 1
        total = sum(item["quantity"] for chunk in chunks for item in chunk)
        assert total == 16000

    def test_each_chunk_under_999(self):
        dl = Downloader(auth_token="dummy", drive_service=None)
        items = [{"msku": "A", "quantity": 3000}]
        chunks = dl._split_by_quantity_limit(items)
        for chunk in chunks:
            chunk_total = sum(item["quantity"] for item in chunk)
            assert chunk_total <= 999
```

- [ ] **Step 6: テストが失敗することを確認**

```bash
cd python && pytest tests/infrastructure/amazon/test_downloader.py -v
```

Expected: FAIL

- [ ] **Step 7: Downloader を実装**

```python
# python/src/infrastructure/amazon/downloader.py
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SP_API_LABELS_URL = "https://sellingpartnerapi-fe.amazon.com/inbound/fba/2024-03-20/items/labels"
MAX_QUANTITY_PER_REQUEST = 999
LABEL_FOLDER_ID = "1ymbSzyiawRaREUwwaNYp4OzoGEOBgDNp"


class Downloader:
    def __init__(self, auth_token: str, drive_service: Any) -> None:
        self._auth_token = auth_token
        self._drive_service = drive_service
        self._headers = {
            "Accept": "application/json",
            "x-amz-access-token": auth_token,
            "Content-Type": "application/json",
        }

    def download_labels(
        self, sku_nums: list[dict[str, Any]], file_name: str
    ) -> dict[str, Any]:
        chunks = self._split_by_quantity_limit(sku_nums)

        if len(chunks) == 1:
            return self._download_single_batch(chunks[0], file_name)

        return self._download_multiple_batches(chunks, file_name)

    def _download_single_batch(
        self, sku_nums: list[dict[str, Any]], file_name: str
    ) -> dict[str, Any]:
        response_json = self._fetch_labels(sku_nums)
        pdf_bytes = self._download_pdf_bytes(response_json)
        url = self._save_to_drive(pdf_bytes, f"{file_name}.pdf")
        return {"url": url, "response_data": response_json}

    def _download_multiple_batches(
        self, chunks: list[list[dict[str, Any]]], file_name: str
    ) -> dict[str, Any]:
        urls: list[str] = []
        last_response: dict[str, Any] = {}

        for i, chunk in enumerate(chunks):
            logger.info("ラベル分割ダウンロード: %d/%d", i + 1, len(chunks))
            response_json = self._fetch_labels(chunk)
            pdf_bytes = self._download_pdf_bytes(response_json)
            url = self._save_to_drive(pdf_bytes, f"{file_name}_part{i + 1}.pdf")
            urls.append(url)
            last_response = response_json

        logger.info("ラベル分割ダウンロード完了: %d件のPDFを作成しました", len(chunks))
        return {"url": urls[0], "urls": urls, "response_data": last_response}

    def _fetch_labels(self, sku_nums: list[dict[str, Any]]) -> dict[str, Any]:
        payload = {
            "labelType": "STANDARD_FORMAT",
            "marketplaceId": "A1VC38T7YXB528",
            "mskuQuantities": sku_nums,
            "localeCode": "ja_JP",
            "pageType": "A4_40_52x29",
        }
        response = httpx.post(
            SP_API_LABELS_URL, json=payload, headers=self._headers, timeout=30.0
        )
        response_json = response.json()
        logger.info("downloadLabels response: %s", response_json)

        if response_json.get("errors"):
            messages = "; ".join(
                f'{e["code"]}: {e["message"]}' for e in response_json["errors"]
            )
            raise RuntimeError(f"SP-API ラベル取得エラー: {messages}")

        if not response_json.get("documentDownloads"):
            raise RuntimeError("SP-API レスポンスにダウンロードURLが含まれていません")

        return response_json

    def _download_pdf_bytes(self, response_json: dict[str, Any]) -> bytes:
        file_uri = response_json["documentDownloads"][0]["uri"]
        response = httpx.get(file_uri, timeout=60.0)
        response.raise_for_status()
        return response.content

    def _save_to_drive(self, pdf_bytes: bytes, file_name: str) -> str:
        from googleapiclient.http import MediaInMemoryUpload

        media = MediaInMemoryUpload(pdf_bytes, mimetype="application/pdf")
        file_metadata = {
            "name": file_name,
            "parents": [LABEL_FOLDER_ID],
        }
        created = (
            self._drive_service.files()
            .create(body=file_metadata, media_body=media, fields="id")
            .execute()
        )
        file_id = created["id"]
        return f"https://drive.google.com/uc?export=download&id={file_id}"

    def _split_by_quantity_limit(
        self, sku_nums: list[dict[str, Any]]
    ) -> list[list[dict[str, Any]]]:
        total_quantity = sum(item["quantity"] for item in sku_nums)

        if total_quantity <= 15000:
            return [sku_nums]

        expanded: list[dict[str, Any]] = []
        for item in sku_nums:
            remaining = item["quantity"]
            while remaining > 0:
                qty = min(remaining, MAX_QUANTITY_PER_REQUEST)
                expanded.append({"msku": item["msku"], "quantity": qty})
                remaining -= qty

        chunks: list[list[dict[str, Any]]] = []
        current_chunk: list[dict[str, Any]] = []
        chunk_total = 0

        for item in expanded:
            if chunk_total + item["quantity"] > MAX_QUANTITY_PER_REQUEST and current_chunk:
                chunks.append(current_chunk)
                current_chunk = []
                chunk_total = 0
            current_chunk.append(item)
            chunk_total += item["quantity"]

        if current_chunk:
            chunks.append(current_chunk)

        logger.info(
            "ラベル数量が上限を超えるため %d 回に分割します", len(chunks)
        )
        return chunks
```

- [ ] **Step 8: テストが通ることを確認**

```bash
cd python && pytest tests/infrastructure/amazon/ -v
```

Expected: 5 passed

- [ ] **Step 9: コミット**

```bash
git add python/src/infrastructure/amazon/auth.py python/src/infrastructure/amazon/downloader.py python/tests/infrastructure/amazon/
git commit -m "feat: SP-API認証とラベルダウンローダーを実装"
```

---

## Task 7: infrastructure層 - FnskuGetter + MerchantListingsSkuResolver

**Files:**
- Create: `python/src/infrastructure/amazon/fnsku_getter.py`
- Create: `python/src/infrastructure/amazon/merchant_listings_sku_resolver.py`
- Test: `python/tests/infrastructure/amazon/test_fnsku_getter.py`
- Test: `python/tests/infrastructure/amazon/test_merchant_listings_sku_resolver.py`

- [ ] **Step 1: FnskuGetter のテストを書く**

```python
# python/tests/infrastructure/amazon/test_fnsku_getter.py
from unittest.mock import patch, MagicMock
from infrastructure.amazon.fnsku_getter import FnskuGetter


class TestFnskuGetter:
    def test_get_fnsku_returns_value(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "summaries": [{"fnSku": "X001ABC123"}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("infrastructure.amazon.fnsku_getter.httpx.get", return_value=mock_response):
            getter = FnskuGetter(auth_token="dummy")
            result = getter.get_fnsku("MY-SKU-1")

        assert result == "X001ABC123"
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
cd python && pytest tests/infrastructure/amazon/test_fnsku_getter.py -v
```

Expected: FAIL

- [ ] **Step 3: FnskuGetter を実装**

```python
# python/src/infrastructure/amazon/fnsku_getter.py
from __future__ import annotations

import logging
import urllib.parse

import httpx

logger = logging.getLogger(__name__)

SELLER_ID = "APS8L6SC4MEPF"
MARKETPLACE_ID = "A1VC38T7YXB528"


class FnskuGetter:
    def __init__(self, auth_token: str) -> None:
        self._auth_token = auth_token
        self._headers = {
            "Accept": "application/json",
            "x-amz-access-token": auth_token,
        }

    def get_fnsku(self, msku: str) -> str:
        encoded_msku = urllib.parse.quote(msku.strip(), safe="")
        url = (
            f"https://sellingpartnerapi-fe.amazon.com/listings/2021-08-01"
            f"/items/{SELLER_ID}/{encoded_msku}"
            f"?marketplaceIds={MARKETPLACE_ID}"
        )
        response = httpx.get(url, headers=self._headers, timeout=30.0)
        response.raise_for_status()
        data = response.json()

        summaries = data.get("summaries", [])
        if not summaries:
            raise RuntimeError(f"FNSKU が見つかりません: {msku}")

        fnsku = summaries[0].get("fnSku", "")
        if not fnsku:
            raise RuntimeError(f"FNSKU が空です: {msku}")

        logger.info("FNSKU取得: %s -> %s", msku, fnsku)
        return fnsku
```

- [ ] **Step 4: テストが通ることを確認**

```bash
cd python && pytest tests/infrastructure/amazon/test_fnsku_getter.py -v
```

Expected: 1 passed

- [ ] **Step 5: MerchantListingsSkuResolver のテストを書く**

```python
# python/tests/infrastructure/amazon/test_merchant_listings_sku_resolver.py
from infrastructure.amazon.merchant_listings_sku_resolver import MerchantListingsSkuResolver


class TestExtractAsinSkuMap:
    def test_parses_tsv_english_headers(self):
        tsv = "item-name\titem-description\tlisting-id\tseller-sku\tprice\tquantity\topen-date\timage-url\titem-is-marketplace\tproduct-id-type\tzsku\tproduct-id\tasin1\n"
        tsv += "Product1\tdesc\tLIST1\tSKU-001\t100\t10\t2024-01-01\t\tY\tASIN\t\tB001\tB001\n"
        tsv += "Product2\tdesc\tLIST2\tSKU-002\t200\t5\t2024-01-02\t\tY\tASIN\t\tB002\tB002\n"

        resolver = MerchantListingsSkuResolver(auth_token="dummy")
        result = resolver._extract_asin_sku_map(tsv, ["B001", "B002"])

        assert result == {"B001": "SKU-001", "B002": "SKU-002"}

    def test_parses_tsv_japanese_headers(self):
        tsv = "商品名\t商品説明\t出品ID\t出品者SKU\t価格\t数量\t出品日\t画像URL\tマーケットプレイス\t商品IDタイプ\tzSKU\t商品ID\tASIN1\n"
        tsv += "商品A\t説明\tLIST1\tSKU-JP-1\t100\t10\t2024-01-01\t\tY\tASIN\t\tB001\tB001\n"

        resolver = MerchantListingsSkuResolver(auth_token="dummy")
        result = resolver._extract_asin_sku_map(tsv, ["B001"])

        assert result == {"B001": "SKU-JP-1"}

    def test_filters_by_requested_asins(self):
        tsv = "item-name\titem-description\tlisting-id\tseller-sku\tprice\tquantity\topen-date\timage-url\titem-is-marketplace\tproduct-id-type\tzsku\tproduct-id\tasin1\n"
        tsv += "P1\td\tL1\tSKU-1\t100\t10\t2024-01-01\t\tY\tASIN\t\tB001\tB001\n"
        tsv += "P2\td\tL2\tSKU-2\t200\t5\t2024-01-02\t\tY\tASIN\t\tB002\tB002\n"

        resolver = MerchantListingsSkuResolver(auth_token="dummy")
        result = resolver._extract_asin_sku_map(tsv, ["B001"])

        assert result == {"B001": "SKU-1"}
        assert "B002" not in result
```

- [ ] **Step 6: テストが失敗することを確認**

```bash
cd python && pytest tests/infrastructure/amazon/test_merchant_listings_sku_resolver.py -v
```

Expected: FAIL

- [ ] **Step 7: MerchantListingsSkuResolver を実装**

```python
# python/src/infrastructure/amazon/merchant_listings_sku_resolver.py
from __future__ import annotations

import gzip
import io
import logging
import time

import httpx

logger = logging.getLogger(__name__)

REPORTS_API_BASE = "https://sellingpartnerapi-fe.amazon.com/reports/2021-06-30"
MARKETPLACE_ID = "A1VC38T7YXB528"
POLL_INTERVAL_SEC = 5
POLL_TIMEOUT_SEC = 90

EN_SKU_HEADER = "seller-sku"
EN_ASIN_HEADER = "asin1"
JA_SKU_HEADER = "出品者SKU"
JA_ASIN_HEADER = "ASIN1"


class MerchantListingsSkuResolver:
    def __init__(self, auth_token: str) -> None:
        self._auth_token = auth_token
        self._headers = {
            "Accept": "application/json",
            "x-amz-access-token": auth_token,
            "Content-Type": "application/json",
        }

    def resolve_skus_by_asins(self, asins: list[str]) -> dict[str, str]:
        report_id = self._create_merchant_listings_report()
        document_id = self._wait_report_done_and_get_document_id(report_id)
        text = self._download_report_document_text(document_id)
        return self._extract_asin_sku_map(text, asins)

    def _create_merchant_listings_report(self) -> str:
        url = f"{REPORTS_API_BASE}/reports"
        payload = {
            "reportType": "GET_MERCHANT_LISTINGS_ALL_DATA",
            "marketplaceIds": [MARKETPLACE_ID],
        }
        response = httpx.post(url, json=payload, headers=self._headers, timeout=30.0)
        response.raise_for_status()
        report_id = response.json()["reportId"]
        logger.info("レポート作成: %s", report_id)
        return report_id

    def _wait_report_done_and_get_document_id(self, report_id: str) -> str:
        url = f"{REPORTS_API_BASE}/reports/{report_id}"
        elapsed = 0

        while elapsed < POLL_TIMEOUT_SEC:
            response = httpx.get(url, headers=self._headers, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            status = data.get("processingStatus", "")

            if status == "DONE":
                document_id = data.get("reportDocumentId", "")
                logger.info("レポート完了: documentId=%s", document_id)
                return document_id
            if status in ("CANCELLED", "FATAL"):
                raise RuntimeError(f"レポートが失敗しました: {status}")

            time.sleep(POLL_INTERVAL_SEC)
            elapsed += POLL_INTERVAL_SEC

        raise TimeoutError(f"レポートがタイムアウトしました ({POLL_TIMEOUT_SEC}秒)")

    def _download_report_document_text(self, document_id: str) -> str:
        url = f"{REPORTS_API_BASE}/documents/{document_id}"
        response = httpx.get(url, headers=self._headers, timeout=30.0)
        response.raise_for_status()
        doc = response.json()

        download_url = doc.get("url", "")
        compression = doc.get("compressionAlgorithm", "")

        dl_response = httpx.get(download_url, timeout=60.0)
        dl_response.raise_for_status()

        content = dl_response.content
        if compression == "GZIP":
            content = gzip.decompress(content)

        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            return content.decode("shift_jis")

    def _extract_asin_sku_map(self, tsv_text: str, asins: list[str]) -> dict[str, str]:
        asin_set = set(asins)
        lines = tsv_text.strip().split("\n")
        if not lines:
            return {}

        headers = lines[0].split("\t")
        headers_lower = [h.strip().lower() for h in headers]

        sku_col = self._find_column(headers, headers_lower, [EN_SKU_HEADER, JA_SKU_HEADER])
        asin_col = self._find_column(headers, headers_lower, [EN_ASIN_HEADER, JA_ASIN_HEADER])

        if sku_col is None or asin_col is None:
            logger.warning("SKUまたはASIN列が見つかりません: %s", headers)
            return {}

        result: dict[str, str] = {}
        for line in lines[1:]:
            cols = line.split("\t")
            if len(cols) <= max(sku_col, asin_col):
                continue
            asin = cols[asin_col].strip()
            sku = cols[sku_col].strip()
            if asin in asin_set and sku and asin not in result:
                result[asin] = sku

        return result

    def _find_column(
        self, headers: list[str], headers_lower: list[str], candidates: list[str]
    ) -> int | None:
        for candidate in candidates:
            candidate_lower = candidate.lower()
            for i, h in enumerate(headers_lower):
                if h == candidate_lower:
                    return i
            for i, h in enumerate(headers):
                if h.strip() == candidate:
                    return i
        return None
```

- [ ] **Step 8: テストが通ることを確認**

```bash
cd python && pytest tests/infrastructure/amazon/ -v
```

Expected: 8 passed

- [ ] **Step 9: コミット**

```bash
git add python/src/infrastructure/amazon/fnsku_getter.py python/src/infrastructure/amazon/merchant_listings_sku_resolver.py python/tests/infrastructure/amazon/
git commit -m "feat: FnskuGetter, MerchantListingsSkuResolverを実装"
```

---

## Task 8: infrastructure層 - InboundPlanCreator

**Files:**
- Create: `python/src/infrastructure/amazon/inbound_plan_creator.py`

- [ ] **Step 1: InboundPlanCreator を実装**

GAS版の608行のInboundPlanCreatorをPythonに移植。SP-API 2024-03-20 + v0フォールバック。

```python
# python/src/infrastructure/amazon/inbound_plan_creator.py
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from shared.config import DEFAULT_MARKETPLACE_ID, SHIP_FROM_ADDRESS

logger = logging.getLogger(__name__)

API_BASE_2024 = "https://sellingpartnerapi-fe.amazon.com/inbound/fba/2024-03-20"
API_BASE_V0 = "https://sellingpartnerapi-fe.amazon.com/fba/inbound/v0"
POLL_INTERVAL_SEC = 5
POLL_TIMEOUT_SEC = 300
MAX_RETRIES = 3


class InboundPlanCreator:
    def __init__(self, auth_token: str) -> None:
        self._auth_token = auth_token
        self._headers = {
            "Accept": "application/json",
            "x-amz-access-token": auth_token,
            "Content-Type": "application/json",
        }

    def create_plan(self, items: dict[str, dict[str, Any]]) -> dict[str, Any]:
        result = self._create_inbound_plan_with_retry(items)
        inbound_plan_id = result.get("inboundPlanId", "")
        operation_id = result.get("operationId", "")

        if operation_id:
            self._wait_operation(operation_id)

        link = f"https://sellercentral.amazon.co.jp/fba/sendtoamazon/confirm_content_step?wf={inbound_plan_id}"
        return {"inboundPlanId": inbound_plan_id, "link": link}

    def _create_inbound_plan_with_retry(self, items: dict[str, dict[str, Any]]) -> dict[str, Any]:
        prep_owner = "AMAZON"
        for attempt in range(MAX_RETRIES):
            body = self._build_create_plan_body(items, prep_owner)
            response = httpx.post(
                f"{API_BASE_2024}/inboundPlans",
                json=body,
                headers=self._headers,
                timeout=30.0,
            )
            data = response.json()

            if response.status_code == 200:
                logger.info("納品プラン作成成功: %s", data)
                return data

            errors = data.get("errors", [])
            if self._is_prep_owner_error(errors) and attempt < MAX_RETRIES - 1:
                prep_owner = "SELLER"
                logger.warning("prepOwnerエラー -> SELLERでリトライ (attempt=%d)", attempt + 1)
                continue

            messages = "; ".join(f'{e.get("code")}: {e.get("message")}' for e in errors)
            raise RuntimeError(f"納品プラン作成エラー: {messages}")

        raise RuntimeError("納品プラン作成: リトライ上限到達")

    def _build_create_plan_body(
        self, items: dict[str, dict[str, Any]], prep_owner: str
    ) -> dict[str, Any]:
        item_list = []
        for sku, info in items.items():
            item_list.append({
                "msku": sku,
                "asin": info.get("asin", ""),
                "quantity": info.get("quantity", 0),
                "labelOwner": info.get("labelOwner", "SELLER"),
                "prepOwner": prep_owner,
            })

        return {
            "marketplaceId": DEFAULT_MARKETPLACE_ID,
            "sourceAddress": SHIP_FROM_ADDRESS,
            "items": item_list,
        }

    def _is_prep_owner_error(self, errors: list[dict[str, Any]]) -> bool:
        return any("prepOwner" in str(e.get("message", "")).lower() for e in errors)

    def _wait_operation(self, operation_id: str) -> dict[str, Any]:
        url = f"{API_BASE_2024}/operations/{operation_id}"
        elapsed = 0

        while elapsed < POLL_TIMEOUT_SEC:
            response = httpx.get(url, headers=self._headers, timeout=30.0)
            data = response.json()
            status = data.get("operationStatus", "")

            if status == "SUCCESS":
                logger.info("オペレーション完了: %s", operation_id)
                return data
            if status in ("FAILED",):
                raise RuntimeError(f"オペレーション失敗: {data}")

            time.sleep(POLL_INTERVAL_SEC)
            elapsed += POLL_INTERVAL_SEC

        raise TimeoutError(f"オペレーションタイムアウト ({POLL_TIMEOUT_SEC}秒)")

    def get_placement_options(self, inbound_plan_id: str) -> dict[str, Any]:
        url = f"{API_BASE_2024}/inboundPlans/{inbound_plan_id}/placementOptions"
        response = httpx.post(url, json={}, headers=self._headers, timeout=30.0)
        data = response.json()
        operation_id = data.get("operationId", "")

        if operation_id:
            result = self._wait_operation(operation_id)
            return result.get("operationProblems", result)

        return data

    def confirm_placement_option(
        self, inbound_plan_id: str, placement_option_id: str
    ) -> dict[str, Any]:
        url = f"{API_BASE_2024}/inboundPlans/{inbound_plan_id}/placementOptions/{placement_option_id}/confirmation"
        response = httpx.post(url, json={}, headers=self._headers, timeout=30.0)
        response.raise_for_status()
        return response.json()

    def list_shipments(self, inbound_plan_id: str) -> list[dict[str, Any]]:
        url = f"{API_BASE_2024}/inboundPlans/{inbound_plan_id}/shipments"
        response = httpx.get(url, headers=self._headers, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        return data.get("shipments", data.get("body", {}).get("shipments", []))

    def get_shipment_status(self, shipment_id: str) -> str:
        url = f"{API_BASE_V0}/shipments/{shipment_id}"
        params = {"MarketplaceId": DEFAULT_MARKETPLACE_ID}
        response = httpx.get(url, params=params, headers=self._headers, timeout=30.0)
        data = response.json()
        payload = data.get("payload", {})
        members = payload.get("ShipmentData", payload.get("MemberList", []))
        if isinstance(members, list) and members:
            return members[0].get("ShipmentStatus", "")
        return ""

    def get_shipment_items(self, shipment_id: str) -> list[dict[str, Any]]:
        # 2024 API
        try:
            url = f"{API_BASE_2024}/shipments/{shipment_id}/items"
            response = httpx.get(url, headers=self._headers, timeout=30.0)
            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])
                if items:
                    return items
        except Exception:
            pass

        # v0 fallback
        url = f"{API_BASE_V0}/shipments/{shipment_id}/items"
        params = {"MarketplaceId": DEFAULT_MARKETPLACE_ID}
        response = httpx.get(url, params=params, headers=self._headers, timeout=30.0)
        data = response.json()
        payload = data.get("payload", {})
        return payload.get("ItemData", [])

    def get_plan_quantity_totals(
        self, inbound_plan_id: str
    ) -> dict[str, Any]:
        shipments = self.list_shipments(inbound_plan_id)
        total_shipped = 0
        total_received = 0
        shipment_ids: list[str] = []

        for s in shipments:
            sid = s.get("shipmentId", "")
            if sid:
                shipment_ids.append(sid)
            items = self.get_shipment_items(sid)
            for item in items:
                total_shipped += int(item.get("QuantityShipped", item.get("quantityShipped", 0)))
                total_received += int(item.get("QuantityReceived", item.get("quantityReceived", 0)))

        return {
            "quantityShipped": total_shipped,
            "quantityReceived": total_received,
            "shipmentIds": shipment_ids,
        }

    def get_packing_group_id(self, inbound_plan_id: str) -> str:
        url = f"{API_BASE_2024}/inboundPlans/{inbound_plan_id}/packingGroups"
        response = httpx.get(url, headers=self._headers, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        groups = data.get("packingGroups", [])
        if not groups:
            raise RuntimeError("packingGroupが見つかりません")
        return groups[0].get("packingGroupId", groups[0]) if isinstance(groups[0], dict) else groups[0]

    def get_packing_group_items(self, inbound_plan_id: str, packing_group_id: str) -> list[dict[str, Any]]:
        url = f"{API_BASE_2024}/inboundPlans/{inbound_plan_id}/packingGroups/{packing_group_id}/items"
        response = httpx.get(url, headers=self._headers, timeout=30.0)
        response.raise_for_status()
        return response.json().get("items", [])

    def set_packing_information(
        self, inbound_plan_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        url = f"{API_BASE_2024}/inboundPlans/{inbound_plan_id}/packingInformation"
        response = httpx.post(url, json=body, headers=self._headers, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        operation_id = data.get("operationId", "")
        if operation_id:
            return self._wait_operation(operation_id)
        return data
```

- [ ] **Step 2: コミット**

```bash
git add python/src/infrastructure/amazon/inbound_plan_creator.py
git commit -m "feat: InboundPlanCreatorを実装"
```

---

## Task 9: infrastructure層 - スプレッドシート派生クラス

**Files:**
- Create: `python/src/infrastructure/spreadsheet/purchase_sheet.py`
- Create: `python/src/infrastructure/spreadsheet/home_shipment_sheet.py`
- Create: `python/src/infrastructure/spreadsheet/work_record_sheet.py`
- Create: `python/src/infrastructure/spreadsheet/instruction_sheet.py`
- Create: `python/src/infrastructure/spreadsheet/inspection_master_repo.py`

- [ ] **Step 1: PurchaseSheet を実装**

```python
# python/src/infrastructure/spreadsheet/purchase_sheet.py
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from infrastructure.amazon.fnsku_getter import FnskuGetter
from infrastructure.amazon.merchant_listings_sku_resolver import MerchantListingsSkuResolver
from infrastructure.spreadsheet.base_sheet import BaseSheet
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository

logger = logging.getLogger(__name__)

HEADER_ROW = 4


class PurchaseSheet(BaseSheet):
    def __init__(self, repo: BaseSheetsRepository, sheet_id: str, sheet_name: str) -> None:
        super().__init__(repo=repo, sheet_id=sheet_id, sheet_name=sheet_name, header_row=HEADER_ROW)

    def aggregate_items(self) -> dict[str, dict[str, Any]]:
        aggregated: dict[str, dict[str, Any]] = {}
        label_owner = "SELLER"

        for row in self.data:
            try:
                sku = str(row.get("SKU") or "").strip()
            except Exception:
                sku = ""
            try:
                asin = str(row.get("ASIN") or "").strip()
            except Exception:
                asin = ""
            try:
                quantity = int(row.get("購入数") or 0)
            except Exception:
                quantity = 0

            if not sku or quantity <= 0:
                logger.warning("納品プラン対象外: sku=%s, quantity=%d", sku, quantity)
                continue

            if sku not in aggregated:
                aggregated[sku] = {
                    "msku": sku,
                    "asin": asin,
                    "quantity": 0,
                    "labelOwner": label_owner,
                }
            aggregated[sku]["quantity"] += quantity

        return aggregated

    def write_plan_result(self, plan_result: dict[str, Any]) -> None:
        plan_col = self._get_column_index_by_name("納品プラン") + 1
        ship_date_col = self._get_column_index_by_name("発送日") + 1

        link = str(plan_result.get("link", ""))
        inbound_plan_id = str(plan_result.get("inboundPlanId", ""))
        today = datetime.now().strftime("%Y/%m/%d")

        for row in self.data:
            row_num = row.row_number
            if link:
                display = inbound_plan_id or self._generate_plan_name_text()
                formula = f'=HYPERLINK("{link}", "{display}")'
                self.write_formula(row_num, plan_col, formula)
            elif inbound_plan_id:
                self.write_cell(row_num, plan_col, inbound_plan_id)

            self.write_cell(row_num, ship_date_col, today)

    def decrease_purchase_quantity(self, quantity: int) -> list[int]:
        qty_col = self._get_column_index_by_name("購入数") + 1
        zero_rows: list[int] = []

        for row in self.data:
            current = int(self._worksheet.cell(row.row_number, qty_col).value or 0)
            new_qty = max(0, current - quantity)
            self.write_cell(row.row_number, qty_col, new_qty)
            logger.info("行%d: 購入数を%dから%dに減らしました", row.row_number, current, new_qty)
            if new_qty == 0:
                zero_rows.append(row.row_number)

        return zero_rows

    def delete_rows(self, row_numbers: list[int]) -> None:
        for row_num in sorted(row_numbers, reverse=True):
            self._worksheet.delete_rows(row_num)
            logger.info("行%dを削除しました", row_num)

    def fetch_missing_fnskus(self, access_token: str) -> None:
        getter = FnskuGetter(access_token)
        fnsku_col_idx = self._get_column_index_by_name("FNSKU")
        fnsku_col = fnsku_col_idx + 1

        for row in self.data:
            fnsku = str(row.get("FNSKU") or "").strip()
            sku = str(row.get("SKU") or "").strip()

            if not fnsku and sku:
                fetched = getter.get_fnsku(sku)
                logger.info("FNSKU取得: %s -> %s", sku, fetched)
                self.write_cell(row.row_number, fnsku_col, fetched)
                row[fnsku_col_idx] = fetched

    def fill_missing_skus_from_asins(self, access_token: str) -> None:
        sku_col_idx = self._get_column_index_by_name("SKU")
        sku_col = sku_col_idx + 1

        asin_to_sku_local = self._build_asin_to_sku_local_map()
        targets = self._collect_missing_sku_targets()

        if not targets:
            logger.info("[SKU補完] SKU空白なし -> スキップ")
            return

        filled_local = 0
        still_missing_asins: list[str] = []
        for t in targets:
            resolved = asin_to_sku_local.get(t["asin"])
            if resolved:
                self.write_cell(t["row_num"], sku_col, resolved)
                t["row"][sku_col_idx] = resolved
                filled_local += 1
            else:
                still_missing_asins.append(t["asin"])

        unique_missing = list(set(still_missing_asins))
        if not unique_missing:
            logger.info("[SKU補完] ローカル流用で全件補完: %d/%d", filled_local, len(targets))
            return

        logger.info("[SKU補完] ローカル=%d/%d -> Reports API (ASIN数=%d)", filled_local, len(targets), len(unique_missing))
        resolver = MerchantListingsSkuResolver(access_token)
        asin_to_sku_remote = resolver.resolve_skus_by_asins(unique_missing)

        filled_remote = 0
        for t in targets:
            current = str(t["row"].get("SKU") or "").strip()
            if current:
                continue
            resolved = asin_to_sku_remote.get(t["asin"])
            if resolved:
                self.write_cell(t["row_num"], sku_col, resolved)
                t["row"][sku_col_idx] = resolved
                filled_remote += 1

        logger.info("[SKU補完] 完了: local=%d, remote=%d, total=%d/%d", filled_local, filled_remote, filled_local + filled_remote, len(targets))

    def write_plan_name_to_rows(self, instruction_url: str | None) -> int:
        date_str = self._format_date_mmdd()

        def value_func(row, _index):
            delivery_category = str(row.get("納品分類") or "").strip()
            plan_name = f"{date_str}{delivery_category}"
            if instruction_url:
                return {"type": "formula", "value": f'=HYPERLINK("{instruction_url}", "{plan_name}")'}
            return plan_name

        return self.write_column_by_func("プラン別名", value_func)

    def _build_asin_to_sku_local_map(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for row in self.all_data:
            sku = str(row.get("SKU") or "").strip()
            asin = str(row.get("ASIN") or "").strip()
            if asin and sku and asin not in result:
                result[asin] = sku
        return result

    def _collect_missing_sku_targets(self) -> list[dict[str, Any]]:
        targets: list[dict[str, Any]] = []
        for row in self.data:
            sku = str(row.get("SKU") or "").strip()
            asin = str(row.get("ASIN") or "").strip()
            if not sku:
                targets.append({"row": row, "row_num": row.row_number, "asin": asin})
        return targets

    def _generate_plan_name_text(self) -> str:
        date_str = self._format_date_mmdd()
        try:
            category = str(self.data[0].get("納品分類") or "").strip() if self.data else ""
        except Exception:
            category = ""
        return f"{date_str}{category}"

    def _format_date_mmdd(self) -> str:
        now = datetime.now()
        return f"{now.month:02d}/{now.day:02d}"
```

- [ ] **Step 2: HomeShipmentSheet を実装**

```python
# python/src/infrastructure/spreadsheet/home_shipment_sheet.py
from __future__ import annotations

from infrastructure.spreadsheet.base_sheet import BaseSheet
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository

HEADER_ROW = 3


class HomeShipmentSheet(BaseSheet):
    def __init__(self, repo: BaseSheetsRepository, sheet_id: str, sheet_name: str) -> None:
        super().__init__(repo=repo, sheet_id=sheet_id, sheet_name=sheet_name, header_row=HEADER_ROW)

    def get_row_numbers_column(self) -> list[str]:
        return [str(row.get("行番号") or "").strip() for row in self.data if row.get("行番号")]

    def get_values(self, column_name: str) -> list[str]:
        return [str(row.get(column_name) or "").strip() for row in self.data]

    def get_defect_reason_list(self) -> list[str]:
        all_values = self._worksheet.get_all_values()
        reasons: list[str] = []
        for row_values in all_values[1:]:
            if len(row_values) >= 19:
                val = str(row_values[18]).strip()
                if val:
                    reasons.append(val)
        return reasons
```

- [ ] **Step 3: WorkRecordSheet を実装**

```python
# python/src/infrastructure/spreadsheet/work_record_sheet.py
from __future__ import annotations

import logging
from typing import Any

from infrastructure.spreadsheet.base_sheet import BaseSheet
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository

logger = logging.getLogger(__name__)


class WorkRecordSheet(BaseSheet):
    def __init__(self, repo: BaseSheetsRepository, sheet_id: str, sheet_name: str) -> None:
        super().__init__(repo=repo, sheet_id=sheet_id, sheet_name=sheet_name, header_row=1)

    def append_record(
        self,
        asin: str,
        purchase_date: str,
        status: str,
        timestamp: str,
        quantity: int | None = None,
        reason: str | None = None,
        comment: str | None = None,
        order_number: str | None = None,
    ) -> None:
        a_col_values = self._worksheet.col_values(1)
        last_a = len(a_col_values) if a_col_values else 0
        new_row = max(2, last_a + 1)

        cells: list[tuple[int, int, Any]] = [
            (new_row, 1, asin),
            (new_row, 2, purchase_date),
            (new_row, 3, status),
            (new_row, 4, timestamp),
        ]
        if quantity is not None:
            cells.append((new_row, 5, quantity))
        if reason is not None:
            cells.append((new_row, 6, reason))
        if comment:
            cells.append((new_row, 7, comment))
        if order_number:
            cells.append((new_row, 8, order_number))

        for r, c, v in cells:
            self._worksheet.update_cell(r, c, v)

        logger.info(
            "作業記録を追加: ASIN=%s, ステータス=%s, 時刻=%s",
            asin, status, timestamp,
        )

    def append_inbound_plan_summary(
        self,
        plan_result: dict[str, Any],
        asin_records: list[dict[str, Any]],
    ) -> None:
        if not asin_records:
            return

        inbound_plan_id = str(plan_result.get("inboundPlanId", "")).strip()
        link = str(plan_result.get("link", "")).strip()

        l_col_values = self._worksheet.col_values(12)
        last_l = len(l_col_values) if l_col_values else 0
        new_row = max(2, last_l + 1)

        from datetime import datetime
        today = datetime.now().strftime("%Y/%m/%d")

        for r in asin_records:
            asin = str(r.get("asin", "")).strip()
            qty = int(r.get("quantity", 0))
            order_no = str(r.get("orderNumber", "")).strip()
            if not asin or qty <= 0:
                continue

            self._worksheet.update_cell(new_row, 11, today)

            if link:
                text = inbound_plan_id or "納品プラン"
                import gspread
                cell_label = gspread.utils.rowcol_to_a1(new_row, 12)
                self._worksheet.update_acell(cell_label, f'=HYPERLINK("{link}", "{text}")')
            else:
                self._worksheet.update_cell(new_row, 12, inbound_plan_id)

            self._worksheet.update_cell(new_row, 13, asin)
            self._worksheet.update_cell(new_row, 14, qty)

            if order_no:
                self._worksheet.update_cell(new_row, 15, order_no)

            new_row += 1
```

- [ ] **Step 4: InstructionSheet を実装**

```python
# python/src/infrastructure/spreadsheet/instruction_sheet.py
from __future__ import annotations

import logging
from typing import Any

import httpx

from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository

logger = logging.getLogger(__name__)

TEMPLATE_ID = "1qd3raNESIc35YvzPoBBwEKEFySDLw0-XZL9bNAcqcus"
START_ROW = 8


class InstructionSheet:
    def __init__(self, repo: BaseSheetsRepository, drive_service: Any, keepa_api_key: str) -> None:
        self._repo = repo
        self._drive_service = drive_service
        self._keepa_api_key = keepa_api_key

    def create(self, data: list[Any]) -> str:
        rows = self._extract_rows(data)
        plan_name = self._generate_plan_name(data)
        file_id, sheet = self._create_sheet_file(plan_name)
        self._write_row_data(sheet, rows)
        return f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx"

    def _extract_rows(self, data: list[Any]) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for row in data:
            fnsku = str(row.get("FNSKU") or "").strip()
            asin = str(row.get("ASIN") or "").strip()
            product_name = str(row.get("商品名") or "").strip()
            quantity = str(row.get("購入数") or "").strip()
            if fnsku:
                rows.append({
                    "fnsku": fnsku,
                    "asin": asin,
                    "product_name": product_name,
                    "quantity": quantity,
                })
        return rows

    def _generate_plan_name(self, data: list[Any]) -> str:
        from datetime import datetime
        now = datetime.now()
        date_str = f"{now.month:02d}/{now.day:02d}"
        try:
            category = str(data[0].get("納品分類") or "").strip() if data else ""
        except Exception:
            category = ""
        return f"{date_str}{category}指示書"

    def _create_sheet_file(self, plan_name: str) -> tuple[str, Any]:
        copied = self._drive_service.files().copy(
            fileId=TEMPLATE_ID,
            body={"name": plan_name},
        ).execute()
        file_id = copied["id"]

        import gspread
        spreadsheet = self._repo.client.open_by_key(file_id)
        sheet = spreadsheet.sheet1
        return file_id, sheet

    def _write_row_data(self, sheet: Any, rows: list[dict[str, str]]) -> None:
        for i, row_data in enumerate(rows):
            row_num = START_ROW + i
            sheet.update_cell(row_num, 1, row_data["fnsku"])
            sheet.update_cell(row_num, 2, row_data["asin"])
            sheet.update_cell(row_num, 3, row_data["product_name"])
            sheet.update_cell(row_num, 4, row_data["quantity"])

            image_url = self._get_product_image(row_data["asin"])
            if image_url:
                formula = f'=IMAGE("{image_url}")'
                import gspread
                cell_label = gspread.utils.rowcol_to_a1(row_num, 5)
                sheet.update_acell(cell_label, formula)

    def _get_product_image(self, asin: str) -> str | None:
        if not asin or not self._keepa_api_key:
            return None
        try:
            url = f"https://api.keepa.com/product?key={self._keepa_api_key}&domain=5&asin={asin}"
            response = httpx.get(url, timeout=30.0)
            data = response.json()
            products = data.get("products", [])
            if not products:
                return None
            images_csv = products[0].get("imagesCSV", "")
            if not images_csv:
                return None
            first_image = images_csv.split(",")[0]
            return f"https://images-na.ssl-images-amazon.com/images/I/{first_image}._SL100_.jpg"
        except Exception as e:
            logger.warning("Keepa画像取得エラー (%s): %s", asin, e)
            return None
```

- [ ] **Step 5: InspectionMasterRepo を実装**

```python
# python/src/infrastructure/spreadsheet/inspection_master_repo.py
from __future__ import annotations

from domain.inspection.entities.inspection_master_item import InspectionMasterItem
from domain.inspection.value_objects.inspection_master_catalog import InspectionMasterCatalog
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository


class InspectionMasterRepo:
    def __init__(self, repo: BaseSheetsRepository, spreadsheet_id: str, sheet_gid: str | None = None) -> None:
        self._repo = repo
        self._spreadsheet_id = spreadsheet_id
        self._sheet_gid = sheet_gid

    def load(self) -> InspectionMasterCatalog:
        spreadsheet = self._repo.open_spreadsheet(self._spreadsheet_id)

        if self._sheet_gid:
            sheet = None
            for ws in spreadsheet.worksheets():
                if str(ws.id) == str(self._sheet_gid):
                    sheet = ws
                    break
            if sheet is None:
                sheet = spreadsheet.sheet1
        else:
            sheet = spreadsheet.sheet1

        all_values = sheet.get_all_values()
        if not all_values:
            return InspectionMasterCatalog(items_by_asin={})

        headers = [str(h).strip() for h in all_values[0]]
        asin_col = 0
        name_col = headers.index("商品名") if "商品名" in headers else 1
        point_col = headers.index("検品箇所") if "検品箇所" in headers else 2
        url_col = headers.index("詳細指示書URL") if "詳細指示書URL" in headers else 3

        items: dict[str, InspectionMasterItem] = {}
        for row_values in all_values[1:]:
            asin = str(row_values[asin_col]).strip() if len(row_values) > asin_col else ""
            if not asin:
                continue
            items[asin] = InspectionMasterItem(
                asin=asin,
                product_name=str(row_values[name_col]).strip() if len(row_values) > name_col else "",
                inspection_point=str(row_values[point_col]).strip() if len(row_values) > point_col else "",
                detail_instruction_url=str(row_values[url_col]).strip() if len(row_values) > url_col else "",
            )

        return InspectionMasterCatalog(items_by_asin=items)
```

- [ ] **Step 6: コミット**

```bash
git add python/src/infrastructure/spreadsheet/
git commit -m "feat: スプレッドシート派生クラス(PurchaseSheet, HomeShipmentSheet等)を実装"
```

---

## Task 10: usecases層 - 全12ユースケース

**Files:**
- Create: `python/src/usecases/print_labels.py`
- Create: `python/src/usecases/inbound_plan.py`
- Create: `python/src/usecases/home_shipment.py`
- Create: `python/src/usecases/work_record.py`
- Create: `python/src/usecases/create_inspection_sheet.py`
- Create: `python/src/usecases/update_status_estimate.py`
- Create: `python/src/usecases/update_inventory_estimate_from_stock.py`
- Create: `python/src/usecases/split_row.py`
- Create: `python/src/usecases/update_arrival_date.py`
- Create: `python/src/usecases/set_filter.py`
- Create: `python/src/usecases/set_packing_info.py`

- [ ] **Step 1: work_record.py を実装**

```python
# python/src/usecases/work_record.py
from __future__ import annotations

import logging
from datetime import datetime

import click

from shared.config import AppConfig
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.home_shipment_sheet import HomeShipmentSheet
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet
from infrastructure.spreadsheet.work_record_sheet import WorkRecordSheet

logger = logging.getLogger(__name__)


def record_work_start(config: AppConfig, repo: BaseSheetsRepository, row_numbers: list[int]) -> None:
    home_sheet = HomeShipmentSheet(repo, config.sheet_id, config.home_shipment_sheet_name)
    home_sheet.get_rows_by_numbers(row_numbers)

    work_record = WorkRecordSheet(repo, config.sheet_id, config.work_record_sheet_name)
    timestamp = datetime.now().strftime("%Y/%m/%d %H:%M:%S")

    for row in home_sheet.data:
        asin = str(row.get("ASIN") or "").strip()
        purchase_date = str(row.get("購入日") or "").strip()
        try:
            order_number = str(row.get("注文番号") or "").strip()
        except Exception:
            order_number = ""

        if not asin:
            logger.warning("ASINが空の行をスキップしました")
            continue

        work_record.append_record(asin, purchase_date, "開始", timestamp, order_number=order_number)

    logger.info("%d件の作業記録（開始）を追加しました", len(home_sheet.data))


def record_work_end(config: AppConfig, repo: BaseSheetsRepository, row_numbers: list[int]) -> None:
    home_sheet = HomeShipmentSheet(repo, config.sheet_id, config.home_shipment_sheet_name)
    home_sheet.get_rows_by_numbers(row_numbers)

    work_record = WorkRecordSheet(repo, config.sheet_id, config.work_record_sheet_name)
    timestamp = datetime.now().strftime("%Y/%m/%d %H:%M:%S")

    for row in home_sheet.data:
        asin = str(row.get("ASIN") or "").strip()
        purchase_date = str(row.get("購入日") or "").strip()
        try:
            order_number = str(row.get("注文番号") or "").strip()
        except Exception:
            order_number = ""

        if not asin:
            logger.warning("ASINが空の行をスキップしました")
            continue

        work_record.append_record(asin, purchase_date, "終了", timestamp, order_number=order_number)

    logger.info("%d件の作業記録（終了）を追加しました", len(home_sheet.data))


def record_defect(config: AppConfig, repo: BaseSheetsRepository, row_numbers: list[int]) -> None:
    home_sheet = HomeShipmentSheet(repo, config.sheet_id, config.home_shipment_sheet_name)
    defect_reasons = home_sheet.get_defect_reason_list()
    if not defect_reasons:
        raise RuntimeError("不良原因リストが見つかりません")

    home_sheet.get_rows_by_numbers(row_numbers)
    if not home_sheet.data:
        raise RuntimeError("選択された行がありません")

    row_info = []
    for row in home_sheet.data:
        try:
            order_number = str(row.get("注文番号") or "").strip()
        except Exception:
            order_number = ""
        row_info.append({
            "purchase_row_number": str(row.get("行番号") or "").strip(),
            "asin": str(row.get("ASIN") or "").strip(),
            "purchase_date": str(row.get("購入日") or "").strip(),
            "order_number": order_number,
        })

    quantity = click.prompt("不良数を入力してください", type=int)
    if quantity <= 0:
        raise ValueError("有効な不良数を入力してください")

    reason_list = "\n".join(f"{i + 1}: {r}" for i, r in enumerate(defect_reasons))
    reason_index = click.prompt(f"原因を番号で選択してください:\n{reason_list}", type=int) - 1
    if reason_index < 0 or reason_index >= len(defect_reasons):
        raise ValueError("有効な番号を入力してください")
    selected_reason = defect_reasons[reason_index]

    comment = click.prompt("コメント（任意、空欄可）", default="", show_default=False) or None

    purchase_row_numbers = [info["purchase_row_number"] for info in row_info if info["purchase_row_number"]]
    purchase_sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    purchase_sheet.filter("行番号", purchase_row_numbers)

    if not purchase_sheet.data:
        raise RuntimeError("仕入管理シートに対応する行が見つかりません")

    zero_rows = purchase_sheet.decrease_purchase_quantity(quantity)
    if zero_rows:
        purchase_sheet.delete_rows(zero_rows)

    work_record = WorkRecordSheet(repo, config.sheet_id, config.work_record_sheet_name)
    timestamp = datetime.now().strftime("%Y/%m/%d %H:%M:%S")

    for info in row_info:
        if not info["asin"]:
            continue
        work_record.append_record(
            info["asin"], info["purchase_date"], "不良", timestamp,
            quantity=quantity, reason=selected_reason, comment=comment,
            order_number=info["order_number"],
        )

    logger.info("%d件の不良品記録を追加しました", len(row_info))
    click.echo(f"不良品登録完了。不良数: {quantity}, 原因: {selected_reason}")
```

- [ ] **Step 2: print_labels.py を実装**

```python
# python/src/usecases/print_labels.py
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import click

from shared.config import AppConfig
from domain.label.services.label_aggregator import LabelAggregator
from infrastructure.amazon.auth import get_auth_token
from infrastructure.amazon.downloader import Downloader
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.instruction_sheet import InstructionSheet
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet
from usecases.create_inspection_sheet import create_inspection_sheet_if_needed

logger = logging.getLogger(__name__)


def generate_labels_and_instructions(
    config: AppConfig, repo: BaseSheetsRepository, drive_service: Any, row_numbers: list[int]
) -> None:
    access_token = get_auth_token(config.api_key, config.api_secret, config.refresh_token)

    sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    sheet.get_rows_by_numbers(row_numbers)

    sheet.fill_missing_skus_from_asins(access_token)
    sheet.fetch_missing_fnskus(access_token)

    inspection_url = create_inspection_sheet_if_needed(config, repo, drive_service, sheet.data)
    if inspection_url:
        sheet.write_formula(2, 3, f'=HYPERLINK("{inspection_url}", "検品シート")')

    label_urls = _create_label_pdf(sheet.data, access_token, drive_service)
    instruction_url = _create_instruction_sheet(config, repo, drive_service, sheet.data)
    _write_to_sheet(sheet, instruction_url, label_urls)


def _create_label_pdf(data: list[Any], access_token: str, drive_service: Any) -> list[str]:
    aggregator = LabelAggregator()
    items = aggregator.aggregate(data)
    downloader = Downloader(auth_token=access_token, drive_service=drive_service)
    date_str = datetime.now().strftime("%Y-%m-%d")
    sku_nums = [item.to_msku_quantity() for item in items]
    result = downloader.download_labels(sku_nums, date_str)

    urls = result.get("urls", [result["url"]])
    if len(urls) > 1:
        click.echo(f"ラベル分割ダウンロード完了: {len(urls)}件のPDFを作成しました")
    return urls


def _create_instruction_sheet(
    config: AppConfig, repo: BaseSheetsRepository, drive_service: Any, data: list[Any]
) -> str:
    instruction = InstructionSheet(repo, drive_service, config.keepa_api_key)
    return instruction.create(data)


def _write_to_sheet(
    sheet: PurchaseSheet, instruction_url: str, label_urls: list[str]
) -> None:
    today = datetime.now().strftime("%Y/%m/%d")
    sheet.write_column_by_func("梱包依頼日", lambda _row, _i: today)

    try:
        sheet.write_plan_name_to_rows(instruction_url)
    except Exception as e:
        logger.warning("プラン別名列への書き込みでエラー: %s", e)

    if len(label_urls) == 1:
        sheet.write_formula(2, 1, f'=HYPERLINK("{label_urls[0]}", "ラベルデータ")')
    else:
        for i, url in enumerate(label_urls):
            sheet.write_formula(2 + i, 1, f'=HYPERLINK("{url}", "ラベル{i + 1}/{len(label_urls)}")')

    sheet.write_formula(2, 2, f'=HYPERLINK("{instruction_url}", "指示書")')
```

- [ ] **Step 3: inbound_plan.py を実装**

```python
# python/src/usecases/inbound_plan.py
from __future__ import annotations

import logging
from typing import Any

import click

from shared.config import AppConfig
from infrastructure.amazon.auth import get_auth_token
from infrastructure.amazon.inbound_plan_creator import InboundPlanCreator
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet
from infrastructure.spreadsheet.work_record_sheet import WorkRecordSheet

logger = logging.getLogger(__name__)


def create_inbound_plan(config: AppConfig, repo: BaseSheetsRepository, row_numbers: list[int]) -> None:
    access_token = get_auth_token(config.api_key, config.api_secret, config.refresh_token)
    sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    sheet.get_rows_by_numbers(row_numbers)
    sheet.fill_missing_skus_from_asins(access_token)

    items = sheet.aggregate_items()
    if not items:
        raise RuntimeError("納品対象のアイテムがありません")

    creator = InboundPlanCreator(access_token)
    plan_result = creator.create_plan(items)

    sheet.write_plan_result(plan_result)
    _record_to_work_record(config, repo, plan_result, sheet)

    click.echo(f"納品プラン作成完了: {plan_result.get('inboundPlanId', '')}")
    click.echo(f"リンク: {plan_result.get('link', '')}")


def create_inbound_plan_with_placement(config: AppConfig, repo: BaseSheetsRepository, row_numbers: list[int]) -> None:
    access_token = get_auth_token(config.api_key, config.api_secret, config.refresh_token)
    sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    sheet.get_rows_by_numbers(row_numbers)
    sheet.fill_missing_skus_from_asins(access_token)

    items = sheet.aggregate_items()
    if not items:
        raise RuntimeError("納品対象のアイテムがありません")

    creator = InboundPlanCreator(access_token)
    plan_result = creator.create_plan(items)
    inbound_plan_id = plan_result.get("inboundPlanId", "")

    options = creator.get_placement_options(inbound_plan_id)
    placement_options = options.get("placementOptions", [])

    if not placement_options:
        click.echo("Placement Optionがありません。デフォルトで続行します。")
    else:
        for i, opt in enumerate(placement_options):
            opt_id = opt.get("placementOptionId", "")
            fees = opt.get("fees", [])
            click.echo(f"  {i + 1}: {opt_id} (fees: {fees})")

        choice = click.prompt("Placement Optionを番号で選択", type=int) - 1
        if 0 <= choice < len(placement_options):
            selected_id = placement_options[choice].get("placementOptionId", "")
            creator.confirm_placement_option(inbound_plan_id, selected_id)
            click.echo(f"Placement Option確定: {selected_id}")

    sheet.write_plan_result(plan_result)
    _record_to_work_record(config, repo, plan_result, sheet)

    click.echo(f"納品プラン作成完了: {inbound_plan_id}")


def _record_to_work_record(
    config: AppConfig, repo: BaseSheetsRepository,
    plan_result: dict[str, Any], sheet: PurchaseSheet,
) -> None:
    asin_records: list[dict[str, Any]] = []
    for row in sheet.data:
        asin = str(row.get("ASIN") or "").strip()
        qty = int(row.get("購入数") or 0)
        try:
            order_no = str(row.get("注文番号") or "").strip()
        except Exception:
            order_no = ""
        if asin and qty > 0:
            asin_records.append({"asin": asin, "quantity": qty, "orderNumber": order_no})

    if asin_records:
        work_record = WorkRecordSheet(repo, config.sheet_id, config.work_record_sheet_name)
        work_record.append_inbound_plan_summary(plan_result, asin_records)
```

- [ ] **Step 4: home_shipment.py を実装**

```python
# python/src/usecases/home_shipment.py
from __future__ import annotations

import logging

from shared.config import AppConfig
from infrastructure.amazon.auth import get_auth_token
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.home_shipment_sheet import HomeShipmentSheet
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet
from usecases.inbound_plan import create_inbound_plan

logger = logging.getLogger(__name__)


def create_inbound_plan_from_home_shipment(
    config: AppConfig, repo: BaseSheetsRepository, row_numbers: list[int]
) -> None:
    home_sheet = HomeShipmentSheet(repo, config.sheet_id, config.home_shipment_sheet_name)
    home_sheet.get_rows_by_numbers(row_numbers)

    purchase_row_numbers = home_sheet.get_row_numbers_column()
    if not purchase_row_numbers:
        raise RuntimeError("行番号が取得できません")

    purchase_sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    purchase_sheet.filter("行番号", purchase_row_numbers)

    purchase_row_nums = [r.row_number for r in purchase_sheet.data]
    create_inbound_plan(config, repo, purchase_row_nums)
```

- [ ] **Step 5: create_inspection_sheet.py を実装**

```python
# python/src/usecases/create_inspection_sheet.py
from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from shared.config import AppConfig
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.inspection_master_repo import InspectionMasterRepo

logger = logging.getLogger(__name__)

INSPECTION_FOLDER_ID = "1ymbSzyiawRaREUwwaNYp4OzoGEOBgDNp"


def create_inspection_sheet_if_needed(
    config: AppConfig, repo: BaseSheetsRepository, drive_service: Any, rows: list[Any]
) -> str | None:
    if not config.inspection_master_sheet_id:
        return None

    asins = list({str(r.get("ASIN") or "").strip() for r in rows if r.get("ASIN")})
    if not asins:
        return None

    master_repo = InspectionMasterRepo(repo, config.inspection_master_sheet_id, config.inspection_master_sheet_gid)
    catalog = master_repo.load()
    filtered = catalog.filter_by_asins(asins)

    if filtered.size() == 0:
        logger.info("検品マスタに該当ASINなし -> スキップ")
        return None

    template_id = config.inspection_template_sheet_id
    if not template_id:
        return None

    copied = drive_service.files().copy(
        fileId=template_id,
        body={"name": "検品シート"},
    ).execute()
    file_id = copied["id"]

    import gspread
    spreadsheet = repo.client.open_by_key(file_id)
    sheet = spreadsheet.sheet1

    row_num = 2
    for asin in filtered.asins():
        item = filtered.get(asin)
        if not item:
            continue
        sheet.update_cell(row_num, 1, item.asin)
        sheet.update_cell(row_num, 2, item.product_name)
        sheet.update_cell(row_num, 3, item.inspection_point)

        image_url = _get_product_image_url(asin, config.keepa_api_key)
        if image_url:
            cell_label = gspread.utils.rowcol_to_a1(row_num, 4)
            sheet.update_acell(cell_label, f'=IMAGE("{image_url}")')

        row_num += 1

    _append_detail_instruction_sheets(spreadsheet, filtered, repo)

    xlsx_url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx"
    logger.info("検品シート作成: %s", xlsx_url)
    return xlsx_url


def _get_product_image_url(asin: str, keepa_api_key: str) -> str | None:
    if not keepa_api_key:
        return None
    try:
        url = f"https://api.keepa.com/product?key={keepa_api_key}&domain=5&asin={asin}"
        response = httpx.get(url, timeout=30.0)
        data = response.json()
        products = data.get("products", [])
        if not products:
            return None
        images_csv = products[0].get("imagesCSV", "")
        if not images_csv:
            return None
        first_image = images_csv.split(",")[0]
        return f"https://images-na.ssl-images-amazon.com/images/I/{first_image}._SL100_.jpg"
    except Exception as e:
        logger.warning("Keepa画像取得エラー (%s): %s", asin, e)
        return None


def _append_detail_instruction_sheets(spreadsheet: Any, catalog: Any, repo: BaseSheetsRepository) -> None:
    for asin in catalog.asins():
        item = catalog.get(asin)
        if not item or not item.detail_instruction_url:
            continue

        parsed = _parse_spreadsheet_url(item.detail_instruction_url)
        if not parsed:
            continue

        try:
            source_ss = repo.client.open_by_key(parsed["spreadsheet_id"])
            if parsed.get("gid"):
                source_sheet = None
                for ws in source_ss.worksheets():
                    if str(ws.id) == str(parsed["gid"]):
                        source_sheet = ws
                        break
                if not source_sheet:
                    source_sheet = source_ss.sheet1
            else:
                source_sheet = source_ss.sheet1

            source_sheet.copy_to(spreadsheet.id)
            logger.info("詳細指示書シート追加: %s", asin)
        except Exception as e:
            logger.warning("詳細指示書コピー失敗 (%s): %s", asin, e)


def _parse_spreadsheet_url(url: str) -> dict[str, str] | None:
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url)
    if not match:
        return None
    result: dict[str, str] = {"spreadsheet_id": match.group(1)}
    gid_match = re.search(r"gid=(\d+)", url)
    if gid_match:
        result["gid"] = gid_match.group(1)
    return result
```

- [ ] **Step 6: update_status_estimate.py を実装**

```python
# python/src/usecases/update_status_estimate.py
from __future__ import annotations

import logging
import re
from typing import Any

from shared.config import AppConfig
from infrastructure.amazon.auth import get_auth_token
from infrastructure.amazon.inbound_plan_creator import InboundPlanCreator
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet

logger = logging.getLogger(__name__)

STATUS_COL = "ステータス推測値"
INVENTORY_COL = "在庫数推測値"
RECEIVED_DATE_COL = "受領日推測値"


def update_status_estimate(config: AppConfig, repo: BaseSheetsRepository) -> None:
    access_token = get_auth_token(config.api_key, config.api_secret, config.refresh_token)
    creator = InboundPlanCreator(access_token)

    sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    sheet.filter("ステータス", ["納品中"])

    if not sheet.data:
        logger.info("納品中の行がありません")
        return

    status_cache: dict[str, str] = {}
    items_cache: dict[str, list[dict[str, Any]]] = {}

    for row in sheet.data:
        plan_cell = str(row.get("納品プラン") or "").strip()
        sku = str(row.get("SKU") or "").strip()
        purchase_qty = int(row.get("購入数") or 0)

        identifier = _extract_plan_identifier(plan_cell)
        if not identifier:
            continue

        shipment_id = identifier.get("shipmentId", "")
        inbound_plan_id = identifier.get("inboundPlanId", "")

        if shipment_id and shipment_id not in status_cache:
            try:
                status_cache[shipment_id] = creator.get_shipment_status(shipment_id)
            except Exception as e:
                logger.warning("shipmentStatus取得失敗 (%s): %s", shipment_id, e)
                continue

        status = status_cache.get(shipment_id, "")
        is_closed = status == "CLOSED"

        all_items = _get_all_items(creator, inbound_plan_id, shipment_id, items_cache)
        qty_shipped, qty_received = _sum_quantities_for_sku(all_items, sku)

        is_received = False
        if is_closed:
            is_received = True
        elif qty_shipped > 0 and qty_received > 0:
            diff_ratio = abs(qty_shipped - qty_received) / qty_shipped
            is_received = diff_ratio <= 0.1

        if is_received:
            row_num = row.row_number
            status_col = sheet._get_column_index_by_name(STATUS_COL) + 1
            inv_col = sheet._get_column_index_by_name(INVENTORY_COL) + 1

            sheet.write_cell(row_num, status_col, "在庫あり")
            received_qty = qty_received if qty_received > 0 else purchase_qty
            sheet.write_cell(row_num, inv_col, received_qty)

            try:
                date_col = sheet._get_column_index_by_name(RECEIVED_DATE_COL) + 1
                from datetime import datetime
                sheet.write_cell(row_num, date_col, datetime.now().strftime("%Y/%m/%d"))
            except ValueError:
                pass

            logger.info("行%d: 納品済み (status=%s, shipped=%d, received=%d)", row_num, status, qty_shipped, qty_received)
        else:
            logger.info("行%d: まだ納品中 (status=%s, shipped=%d, received=%d)", row.row_number, status, qty_shipped, qty_received)


def _extract_plan_identifier(cell_value: str) -> dict[str, str] | None:
    hyperlink_match = re.search(r'HYPERLINK\("([^"]+)"', cell_value)
    url = hyperlink_match.group(1) if hyperlink_match else cell_value

    result: dict[str, str] = {}

    wf_match = re.search(r"wf=(wf[a-zA-Z0-9]+)", url)
    if wf_match:
        result["inboundPlanId"] = wf_match.group(1)

    fba_match = re.search(r"(FBA[A-Z0-9]+)", url)
    if fba_match:
        result["shipmentId"] = fba_match.group(1)

    return result if result else None


def _get_all_items(
    creator: InboundPlanCreator,
    inbound_plan_id: str,
    shipment_id: str,
    cache: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    cache_key = inbound_plan_id or shipment_id
    if cache_key in cache:
        return cache[cache_key]

    items: list[dict[str, Any]] = []
    if inbound_plan_id:
        try:
            shipments = creator.list_shipments(inbound_plan_id)
            for s in shipments:
                sid = s.get("shipmentId", "")
                if sid:
                    items.extend(creator.get_shipment_items(sid))
        except Exception:
            pass

    if not items and shipment_id:
        try:
            items = creator.get_shipment_items(shipment_id)
        except Exception:
            pass

    cache[cache_key] = items
    return items


def _sum_quantities_for_sku(items: list[dict[str, Any]], sku: str) -> tuple[int, int]:
    shipped = 0
    received = 0
    for item in items:
        item_sku = item.get("SellerSKU", item.get("msku", item.get("sellerSku", "")))
        if str(item_sku).strip() == sku:
            shipped += int(item.get("QuantityShipped", item.get("quantityShipped", 0)))
            received += int(item.get("QuantityReceived", item.get("quantityReceived", 0)))
    return shipped, received
```

- [ ] **Step 7: update_inventory_estimate_from_stock.py を実装**

```python
# python/src/usecases/update_inventory_estimate_from_stock.py
from __future__ import annotations

import logging
from typing import Any

from shared.config import AppConfig
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet

logger = logging.getLogger(__name__)

STATUS_COL = "ステータス推測値"
INVENTORY_COL = "在庫数推測値"


def update_inventory_estimate(config: AppConfig, repo: BaseSheetsRepository) -> None:
    asin_to_stock = _load_asin_to_available_stock(repo, config.sheet_id)

    sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    sheet.filter("ステータス", ["在庫あり", "在庫なし"])

    if not sheet.data:
        logger.info("対象行がありません")
        return

    asin_groups: dict[str, list[Any]] = {}
    for row in sheet.data:
        asin = str(row.get("ASIN") or "").strip()
        if asin:
            asin_groups.setdefault(asin, []).append(row)

    status_col = sheet._get_column_index_by_name(STATUS_COL) + 1
    inv_col = sheet._get_column_index_by_name(INVENTORY_COL) + 1

    for asin, rows in asin_groups.items():
        available = asin_to_stock.get(asin, 0)
        remaining = available

        for row in reversed(rows):
            purchase_qty = int(row.get("購入数") or 0)
            estimated = min(purchase_qty, remaining)
            remaining = max(0, remaining - estimated)

            sheet.write_cell(row.row_number, inv_col, estimated)

            new_status = "在庫なし" if estimated == 0 else "在庫あり"
            sheet.write_cell(row.row_number, status_col, new_status)

            logger.info("行%d: ASIN=%s, 在庫推測=%d, ステータス=%s", row.row_number, asin, estimated, new_status)


def _load_asin_to_available_stock(repo: BaseSheetsRepository, sheet_id: str) -> dict[str, int]:
    try:
        spreadsheet = repo.open_spreadsheet(sheet_id)
        stock_sheet = spreadsheet.worksheet("stock")
    except Exception:
        logger.warning("stockシートが見つかりません")
        return {}

    all_values = stock_sheet.get_all_values()
    if not all_values:
        return {}

    headers = [str(h).strip() for h in all_values[0]]
    asin_col = headers.index("ASIN") if "ASIN" in headers else None
    available_col = headers.index("販売可能") if "販売可能" in headers else None

    if asin_col is None or available_col is None:
        logger.warning("stockシートにASINまたは販売可能列がありません")
        return {}

    result: dict[str, int] = {}
    for row_values in all_values[1:]:
        if len(row_values) <= max(asin_col, available_col):
            continue
        asin = str(row_values[asin_col]).strip()
        try:
            stock = int(row_values[available_col])
        except (ValueError, TypeError):
            stock = 0
        if asin:
            result[asin] = result.get(asin, 0) + stock

    return result
```

- [ ] **Step 8: split_row.py を実装**

```python
# python/src/usecases/split_row.py
from __future__ import annotations

import logging

import click

from shared.config import AppConfig
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.home_shipment_sheet import HomeShipmentSheet
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet

logger = logging.getLogger(__name__)


def split_row(config: AppConfig, repo: BaseSheetsRepository, row_numbers: list[int]) -> None:
    home_sheet = HomeShipmentSheet(repo, config.sheet_id, config.home_shipment_sheet_name)
    home_sheet.get_rows_by_numbers(row_numbers)

    purchase_row_numbers = home_sheet.get_row_numbers_column()
    if not purchase_row_numbers:
        raise RuntimeError("行番号が取得できません")

    purchase_sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    purchase_sheet.filter("行番号", purchase_row_numbers)

    if not purchase_sheet.data:
        raise RuntimeError("対応する行が見つかりません")

    delivery_qty = click.prompt("納品数を入力してください", type=int)
    if delivery_qty <= 0:
        raise ValueError("有効な納品数を入力してください")

    qty_col = purchase_sheet._get_column_index_by_name("購入数") + 1

    for row in purchase_sheet.data:
        current_qty = int(purchase_sheet._worksheet.cell(row.row_number, qty_col).value or 0)
        if delivery_qty >= current_qty:
            logger.warning("納品数(%d)が購入数(%d)以上です。スキップ。", delivery_qty, current_qty)
            continue

        new_qty = current_qty - delivery_qty
        purchase_sheet.write_cell(row.row_number, qty_col, new_qty)

        purchase_sheet._worksheet.insert_row(
            [row[i] for i in range(len(row))],
            row.row_number + 1,
        )
        purchase_sheet.write_cell(row.row_number + 1, qty_col, delivery_qty)

        logger.info("行%d: %d -> %d + %d", row.row_number, current_qty, new_qty, delivery_qty)

    click.echo("行分割完了")
```

- [ ] **Step 9: update_arrival_date.py を実装**

```python
# python/src/usecases/update_arrival_date.py
from __future__ import annotations

import logging
from datetime import datetime

from shared.config import AppConfig
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.home_shipment_sheet import HomeShipmentSheet
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet

logger = logging.getLogger(__name__)


def update_arrival_date(config: AppConfig, repo: BaseSheetsRepository, row_numbers: list[int]) -> None:
    home_sheet = HomeShipmentSheet(repo, config.sheet_id, config.home_shipment_sheet_name)
    home_sheet.get_rows_by_numbers(row_numbers)

    tracking_numbers = home_sheet.get_values("追跡番号")
    if not tracking_numbers:
        raise RuntimeError("追跡番号が取得できません")

    purchase_sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    purchase_sheet.filter("追跡番号", tracking_numbers)

    today = datetime.now().strftime("%Y/%m/%d")
    purchase_sheet.write_column_by_func("自宅到着日", lambda _row, _i: today)

    logger.info("%d行の自宅到着日を更新しました", len(purchase_sheet.data))
```

- [ ] **Step 10: set_filter.py を実装**

```python
# python/src/usecases/set_filter.py
from __future__ import annotations

import logging

from shared.config import AppConfig
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository

logger = logging.getLogger(__name__)


def set_filter(config: AppConfig, repo: BaseSheetsRepository) -> None:
    worksheet = repo.open_worksheet(config.sheet_id, config.purchase_sheet_name)
    filter_value = str(worksheet.cell(2, 5).value or "").strip()

    if not filter_value:
        logger.info("E2が空のためフィルタ設定をスキップ")
        return

    logger.info("フィルタ設定: %s", filter_value)
    # gspreadではBasicFilterの直接操作が限定的なため、
    # Sheets APIを使う場合はgoogle-api-python-clientで実装
    logger.warning("gspreadではフィルタ設定機能が限定的です。手動設定を推奨します。")
```

- [ ] **Step 11: set_packing_info.py を実装**

```python
# python/src/usecases/set_packing_info.py
from __future__ import annotations

import logging
import re
from typing import Any

import click

from shared.config import AppConfig
from infrastructure.amazon.auth import get_auth_token
from infrastructure.amazon.inbound_plan_creator import InboundPlanCreator
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet

logger = logging.getLogger(__name__)


def set_packing_info(config: AppConfig, repo: BaseSheetsRepository, row_numbers: list[int]) -> None:
    access_token = get_auth_token(config.api_key, config.api_secret, config.refresh_token)
    sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    sheet.get_rows_by_numbers(row_numbers)

    plan_cell = str(sheet.data[0].get("納品プラン") or "").strip() if sheet.data else ""
    inbound_plan_id = _extract_inbound_plan_id(plan_cell)
    if not inbound_plan_id:
        raise RuntimeError("納品プランIDが取得できません")

    click.echo(f"納品プランID: {inbound_plan_id}")
    click.echo("箱情報を入力してください（例: 1-2：60*40*32 29.1KG）")
    click.echo("空行で入力終了:")

    lines: list[str] = []
    while True:
        line = input()
        if not line.strip():
            break
        lines.append(line)

    carton_text = "\n".join(lines)
    cartons = _parse_carton_input(carton_text)

    if not cartons:
        raise RuntimeError("箱情報がパースできません")

    creator = InboundPlanCreator(access_token)
    packing_group_id = creator.get_packing_group_id(inbound_plan_id)
    items = creator.get_packing_group_items(inbound_plan_id, packing_group_id)

    body = _build_packing_body(packing_group_id, cartons, items)
    creator.set_packing_information(inbound_plan_id, body)

    click.echo("梱包情報の送信が完了しました")


def _extract_inbound_plan_id(cell_value: str) -> str:
    match = re.search(r"wf=(wf[a-zA-Z0-9]+)", cell_value)
    if match:
        return match.group(1)
    match = re.search(r"(wf[a-zA-Z0-9]+)", cell_value)
    return match.group(1) if match else ""


def _parse_carton_input(text: str) -> list[dict[str, Any]]:
    cartons: list[dict[str, Any]] = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue

        match = re.match(
            r"(\d+(?:-\d+)?)\s*[：:]\s*(\d+(?:\.\d+)?)\s*[*×x]\s*(\d+(?:\.\d+)?)\s*[*×x]\s*(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s*[Kk][Gg]",
            line,
        )
        if not match:
            logger.warning("パース失敗: %s", line)
            continue

        box_range = match.group(1)
        length_cm = float(match.group(2))
        width_cm = float(match.group(3))
        height_cm = float(match.group(4))
        weight_kg = float(match.group(5))

        if "-" in box_range:
            start, end = box_range.split("-")
            count = int(end) - int(start) + 1
        else:
            count = 1

        cartons.append({
            "count": count,
            "length": _cm_to_inches(length_cm),
            "width": _cm_to_inches(width_cm),
            "height": _cm_to_inches(height_cm),
            "weight": _kg_to_lbs(weight_kg),
        })

    return cartons


def _cm_to_inches(cm: float) -> float:
    return round(cm / 2.54, 2)


def _kg_to_lbs(kg: float) -> float:
    return round(kg * 2.20462, 2)


def _build_packing_body(
    packing_group_id: str,
    cartons: list[dict[str, Any]],
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    package_groups = []
    for carton in cartons:
        package_groups.append({
            "packingGroupId": packing_group_id,
            "boxes": [{
                "weight": {"unit": "LB", "value": carton["weight"]},
                "dimensions": {
                    "unitOfMeasurement": "IN",
                    "length": carton["length"],
                    "width": carton["width"],
                    "height": carton["height"],
                },
                "quantity": carton["count"],
                "items": [
                    {"msku": item.get("msku", ""), "quantity": item.get("quantity", 0)}
                    for item in items
                ],
            }],
        })

    return {"packageGroupings": package_groups}
```

- [ ] **Step 12: コミット**

```bash
git add python/src/usecases/
git commit -m "feat: 全12ユースケースを実装"
```

---

## Task 11: CLIエントリーポイント (main.py)

**Files:**
- Create: `python/main.py`
- Create: `python/tests/conftest.py`

- [ ] **Step 1: main.py を実装**

```python
# python/main.py
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import click

from shared.config import AppConfig
from shared.logging import setup_logging
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository


def _get_config_and_repo() -> tuple[AppConfig, BaseSheetsRepository]:
    config = AppConfig.from_dotenv()
    repo = BaseSheetsRepository(config.credentials_file)
    return config, repo


def _get_drive_service(config: AppConfig) -> object:
    from oauth2client.service_account import ServiceAccountCredentials
    from googleapiclient.discovery import build

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(config.credentials_file, scope)
    return build("drive", "v3", credentials=creds)


@click.group()
def cli() -> None:
    setup_logging()


@cli.command()
@click.argument("row_numbers", nargs=-1, type=int, required=True)
def print_labels(row_numbers: tuple[int, ...]) -> None:
    from usecases.print_labels import generate_labels_and_instructions
    config, repo = _get_config_and_repo()
    drive_service = _get_drive_service(config)
    generate_labels_and_instructions(config, repo, drive_service, list(row_numbers))


@cli.command()
@click.argument("row_numbers", nargs=-1, type=int, required=True)
def create_inbound_plan(row_numbers: tuple[int, ...]) -> None:
    from usecases.inbound_plan import create_inbound_plan as _create
    config, repo = _get_config_and_repo()
    _create(config, repo, list(row_numbers))


@cli.command()
@click.argument("row_numbers", nargs=-1, type=int, required=True)
def create_inbound_plan_placement(row_numbers: tuple[int, ...]) -> None:
    from usecases.inbound_plan import create_inbound_plan_with_placement
    config, repo = _get_config_and_repo()
    create_inbound_plan_with_placement(config, repo, list(row_numbers))


@cli.command()
@click.argument("row_numbers", nargs=-1, type=int, required=True)
def create_plan_from_home(row_numbers: tuple[int, ...]) -> None:
    from usecases.home_shipment import create_inbound_plan_from_home_shipment
    config, repo = _get_config_and_repo()
    create_inbound_plan_from_home_shipment(config, repo, list(row_numbers))


@cli.command()
@click.option("--type", "record_type", type=click.Choice(["start", "end"]), required=True)
@click.argument("row_numbers", nargs=-1, type=int, required=True)
def work_record(record_type: str, row_numbers: tuple[int, ...]) -> None:
    from usecases.work_record import record_work_start, record_work_end
    config, repo = _get_config_and_repo()
    if record_type == "start":
        record_work_start(config, repo, list(row_numbers))
    else:
        record_work_end(config, repo, list(row_numbers))


@cli.command()
@click.argument("row_numbers", nargs=-1, type=int, required=True)
def defect(row_numbers: tuple[int, ...]) -> None:
    from usecases.work_record import record_defect
    config, repo = _get_config_and_repo()
    record_defect(config, repo, list(row_numbers))


@cli.command()
def update_status() -> None:
    from usecases.update_status_estimate import update_status_estimate
    config, repo = _get_config_and_repo()
    update_status_estimate(config, repo)


@cli.command()
def update_inventory() -> None:
    from usecases.update_inventory_estimate_from_stock import update_inventory_estimate
    config, repo = _get_config_and_repo()
    update_inventory_estimate(config, repo)


@cli.command()
@click.argument("row_numbers", nargs=-1, type=int, required=True)
def split_row(row_numbers: tuple[int, ...]) -> None:
    from usecases.split_row import split_row as _split
    config, repo = _get_config_and_repo()
    _split(config, repo, list(row_numbers))


@cli.command()
@click.argument("row_numbers", nargs=-1, type=int, required=True)
def arrival_date(row_numbers: tuple[int, ...]) -> None:
    from usecases.update_arrival_date import update_arrival_date
    config, repo = _get_config_and_repo()
    update_arrival_date(config, repo, list(row_numbers))


@cli.command()
def set_filter() -> None:
    from usecases.set_filter import set_filter as _set
    config, repo = _get_config_and_repo()
    _set(config, repo)


@cli.command()
@click.argument("row_numbers", nargs=-1, type=int, required=True)
def packing_info(row_numbers: tuple[int, ...]) -> None:
    from usecases.set_packing_info import set_packing_info
    config, repo = _get_config_and_repo()
    set_packing_info(config, repo, list(row_numbers))


if __name__ == "__main__":
    cli()
```

- [ ] **Step 2: conftest.py を作成**

```python
# python/tests/conftest.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
```

- [ ] **Step 3: CLIヘルプが表示されることを確認**

```bash
cd python && python main.py --help
```

Expected: Usage情報とサブコマンド一覧が表示される

- [ ] **Step 4: 全テストが通ることを確認**

```bash
cd python && pytest -v
```

Expected: 全テストがPASS

- [ ] **Step 5: コミット**

```bash
git add python/main.py python/tests/conftest.py
git commit -m "feat: CLIエントリーポイントを実装"
```

---

## Task 12: .env設定 + 最終確認

**Files:**
- Create: `python/.env` (既存の.envから値をコピー)
- Modify: `python/.gitignore`

- [ ] **Step 1: python/.gitignore を作成**

```
# python/.gitignore
__pycache__/
*.pyc
.env
service_account.json
credentials.json
*.egg-info/
dist/
build/
.pytest_cache/
```

- [ ] **Step 2: .envを作成（既存の値を使用）**

既存の `/Users/wadaatsushi/Documents/automation/procurements/management-helper/.env` の値を `python/.env` にコピーし、`GOOGLE_CREDENTIALS_FILE` を追加する。

```bash
cd python
cp ../.env .env
echo "GOOGLE_CREDENTIALS_FILE=service_account.json" >> .env
```

- [ ] **Step 3: service_account.json をpython/に配置（またはシンボリックリンク）**

```bash
# 既存のサービスアカウントファイルへのリンク
ln -s /path/to/your/service_account.json python/service_account.json
```

- [ ] **Step 4: 全テストを実行**

```bash
cd python && pytest -v
```

Expected: 全テストPASS

- [ ] **Step 5: CLIコマンド一覧を確認**

```bash
cd python && python main.py --help
```

Expected:
```
Commands:
  arrival-date
  create-inbound-plan
  create-inbound-plan-placement
  create-plan-from-home
  defect
  packing-info
  print-labels
  set-filter
  split-row
  update-inventory
  update-status
  work-record
```

- [ ] **Step 6: コミット**

```bash
git add python/.gitignore python/.env.example
git commit -m "feat: Python版プロジェクトの初期セットアップ完了"
```
