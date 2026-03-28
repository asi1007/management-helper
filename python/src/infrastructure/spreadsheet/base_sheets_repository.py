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
