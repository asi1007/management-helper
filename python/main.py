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


def _get_drive_service(_config: AppConfig) -> object:
    import os
    from pathlib import Path
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    scopes = ["https://www.googleapis.com/auth/drive"]
    python_dir = Path(__file__).resolve().parent
    token_path = python_dir / "token.json"
    client_secret_path = python_dir / "client_secret.json"

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        else:
            if not client_secret_path.exists():
                raise FileNotFoundError(
                    f"{client_secret_path} が見つかりません。"
                    "Google Cloud ConsoleでOAuth2クライアントID（デスクトップアプリ）を作成し、"
                    "JSONをダウンロードして python/client_secret.json に配置してください。"
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), scopes)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())

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
@click.option("--categories", type=str, default=None, help="納品分類をカンマ区切りで指定（例: ノーマル,ファッション）")
def batch_labels(categories: str | None) -> None:
    from usecases.batch_print_labels import batch_print_labels
    category_list = [c.strip() for c in categories.split(",") if c.strip()] if categories else None
    config, repo = _get_config_and_repo()
    batch_print_labels(config, repo, category_filter=category_list)


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
