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

GDRIVE_BASE = "/Users/wadaatsushi/Library/CloudStorage/GoogleDrive-zyanzyakazyan@gmail.com/マイドライブ/work/shop/invoices/0828 ■共有 新白岡輸入販売×TAXLAB/業務用書類/8.指示書"
DEFAULT_LABEL_DIR = f"{GDRIVE_BASE}/ラベル"
DEFAULT_INSTRUCTION_DIR = f"{GDRIVE_BASE}/検品指示書"
DEFAULT_DETAIL_INSPECTION_DIR = f"{GDRIVE_BASE}/イーウー詳細検品"


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
    label_dir: str
    instruction_dir: str
    detail_inspection_dir: str
    chatwork_api_token: str
    chatwork_room_id: str
    chatwork_to_account_id: str

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
            label_dir=os.getenv("LABEL_DIR", DEFAULT_LABEL_DIR),
            instruction_dir=os.getenv("INSTRUCTION_DIR", DEFAULT_INSTRUCTION_DIR),
            detail_inspection_dir=os.getenv("DETAIL_INSPECTION_DIR", DEFAULT_DETAIL_INSPECTION_DIR),
            chatwork_api_token=os.getenv("CHATWORK_API_TOKEN", ""),
            chatwork_room_id=os.getenv("CHATWORK_ROOM_ID", ""),
            chatwork_to_account_id=os.getenv("CHATWORK_TO_ACCOUNT_ID", ""),
        )

    @classmethod
    def from_dotenv(cls, *, dotenv_path: str | None = None) -> AppConfig:
        load_dotenv(dotenv_path=dotenv_path)
        return cls.from_env()
