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

# 納品分類の判定に使う代表SKU。
# 「売上/日」の納品分類ラベルには実績のない予想値が混ざるため、そこからは選ばない。
# ここに載せるのは専用FCへの納品実績があるSKUだけ:
#   ノーマル専用FC = XJE1 / XKX4、ファッション専用FC = TYO2 / NRT5 / QCB3
#   （QCB5・XJE2・XJW1 は両分類を受け入れるので判定の根拠にならない）
# 廃番などで使えなくなったら次の候補へ自動でフォールバックする。
# 候補の洗い直しは docs の「納品分類の判定」を参照。
DELIVERY_CATEGORY_REFERENCE_SKUS = {
    "ノーマル": ["22-885D-4NIK", "3B-HK6Q-DN3X", "2Z-831G-H2V0", "3Q-FTBT-Q3HG"],
    "ファッション": ["CT-P7KS-ZB0P", "JG-THN3-HCFH", "NH-VABG-H0FL", "8E-3VEB-P3I9"],
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
    keepa_api_key: str
    label_dir: str
    instruction_dir: str
    detail_inspection_dir: str
    chatwork_api_token: str
    chatwork_room_id: str
    chatwork_to_account_id: str
    todoist_api_token: str
    todoist_project: str

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
            keepa_api_key=os.getenv("KEEPA_API_KEY", ""),
            label_dir=os.getenv("LABEL_DIR", DEFAULT_LABEL_DIR),
            instruction_dir=os.getenv("INSTRUCTION_DIR", DEFAULT_INSTRUCTION_DIR),
            detail_inspection_dir=os.getenv("DETAIL_INSPECTION_DIR", DEFAULT_DETAIL_INSPECTION_DIR),
            chatwork_api_token=os.getenv("CHATWORK_API_TOKEN", ""),
            chatwork_room_id=os.getenv("CHATWORK_ROOM_ID", ""),
            chatwork_to_account_id=os.getenv("CHATWORK_TO_ACCOUNT_ID", ""),
            todoist_api_token=os.getenv("TODOIST_API_TOKEN", ""),
            todoist_project=os.getenv("TODOIST_PROJECT", "INBOX"),
        )

    @classmethod
    def from_dotenv(cls, *, dotenv_path: str | None = None) -> AppConfig:
        load_dotenv(dotenv_path=dotenv_path)
        return cls.from_env()
