from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))


def _add_shared_libraries_to_path() -> None:
    """automation/shared/*/src を import できるようにする。

    .venv を持たないので site-packages への symlink が使えない。
    launchd はラッパーが PYTHONPATH を通すが、手で叩くときは何も通らないため
    ここで自力で解決する（2026-09-14 に amazon_api が見つからず全コマンドが止まった）。
    """
    default_root = Path(__file__).resolve().parents[3] / "shared"
    shared_root = Path(os.environ.get("AUTOMATION_SHARED_ROOT", default_root))
    for library in sorted(shared_root.glob("*/src")):
        path = str(library)
        if path not in sys.path:
            sys.path.insert(0, path)


_add_shared_libraries_to_path()

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
@click.option("--dry-run", is_flag=True, help="タスクを作らず対象だけ表示する")
def notify_launch_ready(dry_run: bool) -> None:
    from usecases.notify_launch_ready import list_launch_ready, notify_launch_ready as run
    config, repo = _get_config_and_repo()
    if dry_run:
        for product in list_launch_ready(config, repo):
            click.echo(f"{product.asin} 受領日{product.received_date} 在庫{product.inventory_quantity} {product.product_name}")
        return
    created = run(config, repo)
    click.echo(f"販売開始タスク: {created}件")


@cli.command()
@click.option("--execute", is_flag=True, help="指定しない場合は検出のみで削除しない")
def delete_blank_rows(execute: bool) -> None:
    from usecases.delete_blank_rows import delete_blank_rows as run
    config, repo = _get_config_and_repo()
    rows = run(config, repo, dry_run=not execute)
    click.echo(f"空白行: {rows}")
    if not execute and rows:
        click.echo("削除するには --execute を付けて再実行してください")


@cli.command()
def archive_out_of_stock() -> None:
    from usecases.archive_out_of_stock import archive_out_of_stock as _archive
    config, repo = _get_config_and_repo()
    _archive(config, repo)


@cli.command()
def fill_sku_fnsku() -> None:
    from usecases.fill_sku_fnsku_from_shipment import fill_sku_fnsku_from_shipment
    config, repo = _get_config_and_repo()
    fill_sku_fnsku_from_shipment(config, repo)


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
@click.option("--air", is_flag=True, help="空輸。プラン別名の末尾に「空輸」を付ける")
@click.option("--rows", type=str, default=None, help="仕入管理シートの行番号をカンマ区切りで指定（空輸と海上を分けて出すとき）")
def batch_labels(categories: str | None, air: bool, rows: str | None) -> None:
    from usecases.batch_print_labels import batch_print_labels
    category_list = [c.strip() for c in categories.split(",") if c.strip()] if categories else None
    row_numbers = [int(r.strip()) for r in rows.split(",") if r.strip()] if rows else None
    config, repo = _get_config_and_repo()
    batch_print_labels(
        config,
        repo,
        category_filter=category_list,
        plan_name_suffix="空輸" if air else "",
        row_numbers=row_numbers,
    )


@cli.command()
@click.option("--rows", type=str, default=None, help="仕入管理シートの行番号をカンマ区切りで指定")
@click.option("--overwrite", is_flag=True, help="既に備考がある行も差し替える（既定は空欄だけ）")
@click.option("--dry-run", is_flag=True, help="書かずに対象だけ表示")
def sync_remarks(rows: str | None, overwrite: bool, dry_run: bool) -> None:
    from usecases.sync_remarks import sync_remarks as run
    row_numbers = [int(r.strip()) for r in rows.split(",") if r.strip()] if rows else None
    config, repo = _get_config_and_repo()
    run(config, repo, row_numbers=row_numbers, overwrite=overwrite, dry_run=dry_run)


@cli.command()
def new_product_shipments() -> None:
    from usecases.new_product_shipment import list_new_product_shipments
    config, repo = _get_config_and_repo()
    list_new_product_shipments(config, repo)


@cli.command()
@click.option("--stale-days", type=int, default=14, help="この日数を超えたら滞留として印を付ける（既定14日）")
def delivery_status(stale_days: int) -> None:
    from usecases.delivery_status import show_delivery_status
    config, repo = _get_config_and_repo()
    show_delivery_status(config, repo, stale_days=stale_days)


@cli.command()
@click.option("--alias", required=True, help="巻き戻す「プラン別名」（例: 09/09ノーマル）")
@click.option("--execute", is_flag=True, help="指定しない場合はドライラン")
@click.option("--delete-chatwork", is_flag=True, help="Chatworkへ送った指示書の投稿も取り下げる")
@click.option("--since-hours", type=int, default=24, help="Chatworkを遡る時間（既定24時間）")
def revert_shipment(alias: str, execute: bool, delete_chatwork: bool, since_hours: int) -> None:
    from usecases.revert_shipment_request import revert_shipment_request
    config, repo = _get_config_and_repo()
    revert_shipment_request(
        config, repo, alias,
        dry_run=not execute,
        delete_chatwork=delete_chatwork,
        since_hours=since_hours,
    )


@cli.command()
def set_filter() -> None:
    from usecases.set_filter import set_filter as _set
    config, repo = _get_config_and_repo()
    _set(config, repo)


@cli.command()
@click.option("--threshold-days", type=int, default=21, help="この日数を超えて未受領なら問い合わせ対象（既定21日）")
@click.option("--send", is_flag=True, help="指定するとChatworkへ問い合わせ文を送信する")
def inquire_undelivered(threshold_days: int, send: bool) -> None:
    from usecases.inquire_undelivered import inquire_undelivered as _inquire
    config, repo = _get_config_and_repo()
    _inquire(config, repo, threshold_days=threshold_days, send=send)


@cli.command()
@click.option("--cartons", required=True, help="箱情報（例: '1：50*40*23 18KG'、複数行は改行区切り）")
@click.option("--ship-date", default=None, help="出荷日 YYYY-MM-DD（省略時は翌日）")
@click.option("--lead-days", type=int, default=None, help="到着予定までの日数（省略時は出荷日の1ヶ月後）")
@click.argument("row_numbers", nargs=-1, type=int, required=True)
def confirm_shipment(
    cartons: str, ship_date: str | None, lead_days: int | None, row_numbers: tuple[int, ...],
) -> None:
    from datetime import date, timedelta
    from usecases.confirm_inbound_shipment import confirm_inbound_shipment
    config, repo = _get_config_and_repo()
    parsed_ship_date = date.fromisoformat(ship_date) if ship_date else date.today() + timedelta(days=1)
    result = confirm_inbound_shipment(
        config, repo, list(row_numbers),
        carton_text=cartons.replace("\\n", "\n"),
        ship_date=parsed_ship_date,
        lead_days=lead_days,
    )
    click.echo(f"納品番号: {result['shipmentConfirmationId']} / 納品先: {result['destination']}")
    window = result["deliveryWindow"]
    click.echo(f"配送ウィンドウ: {str(window.get('startDate'))[:10]} 〜 {str(window.get('endDate'))[:10]}")


@cli.command()
@click.argument("row_numbers", nargs=-1, type=int, required=True)
def packing_info(row_numbers: tuple[int, ...]) -> None:
    from usecases.set_packing_info import set_packing_info
    config, repo = _get_config_and_repo()
    set_packing_info(config, repo, list(row_numbers))


@cli.command()
@click.option("--overwrite", is_flag=True, help="納品分類が既に入っていても再判定して上書きする")
@click.option("--dry-run", is_flag=True, help="判定するが売上/日シートには書き込まない")
@click.argument("asins", nargs=-1, required=True)
def classify_delivery(asins: tuple[str, ...], overwrite: bool, dry_run: bool) -> None:
    from usecases.classify_delivery_category import run_classification
    config, repo = _get_config_and_repo()
    outcomes = run_classification(
        config, repo, list(asins), overwrite=overwrite, dry_run=dry_run
    )
    _echo_classification_outcomes(outcomes)


def _echo_classification_outcomes(outcomes: list) -> None:
    failed = 0
    for outcome in outcomes:
        if outcome.error:
            failed += 1
            click.echo(f"✗ {outcome.asin}: {outcome.error}", err=True)
            continue
        result = outcome.result
        suffix = "（設定済みのためスキップ）" if result.skipped else ""
        if result.cancel_failed:
            suffix += f" ※試作プラン {result.inbound_plan_id} の削除に失敗。Seller Centralで手動削除してください"
        click.echo(f"✓ {outcome.asin}: {result.category}{suffix}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
