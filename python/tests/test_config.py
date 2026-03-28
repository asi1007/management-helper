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
