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
