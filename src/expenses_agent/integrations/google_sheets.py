from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol, cast

import google.auth
from google.auth.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build  # type: ignore[import-untyped]

from expenses_agent.domain.expenses import (
    ExpensePatch,
    ExpenseQuery,
    ExpenseRow,
    SheetRecord,
)

SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
EXPECTED_HEADERS = ["Date", "Expense", "Cost", "Paid By", "Settled", "Category", "Notes"]


class SheetsGateway(Protocol):
    async def append(self, expense: ExpenseRow) -> SheetRecord: ...

    async def search(self, query: ExpenseQuery) -> list[SheetRecord]: ...

    async def update(self, record: SheetRecord, patch: ExpensePatch) -> SheetRecord: ...


def row_matches(expense: ExpenseRow, query: ExpenseQuery) -> bool:
    if query.month and expense.worksheet != query.month:
        return False
    if query.start_date and expense.date < query.start_date:
        return False
    if query.end_date and expense.date > query.end_date:
        return False
    if (
        query.expense_contains
        and query.expense_contains.casefold() not in expense.expense.casefold()
    ):
        return False
    if query.cost is not None and expense.cost != query.cost:
        return False
    if query.paid_by is not None and expense.paid_by != query.paid_by:
        return False
    if query.settled is not None and expense.settled != query.settled:
        return False
    return query.category is None or expense.category == query.category


class GoogleSheetsGateway:
    """Small async facade over the synchronous Google Sheets v4 client."""

    def __init__(self, credentials_path: str | None, spreadsheet_id: str) -> None:
        credentials = load_google_credentials(credentials_path)
        self._service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        self._spreadsheet_id = spreadsheet_id

    async def append(self, expense: ExpenseRow) -> SheetRecord:
        result = await asyncio.to_thread(self._append_sync, expense)
        updated_range = result.get("updates", {}).get("updatedRange", "")
        row_number = _row_number_from_range(updated_range)
        return SheetRecord(worksheet=expense.worksheet, row_number=row_number, expense=expense)

    def _append_sync(self, expense: ExpenseRow) -> dict[str, Any]:
        result = (
            self._service.spreadsheets()
            .values()
            .append(
                spreadsheetId=self._spreadsheet_id,
                range=f"'{expense.worksheet}'!A:G",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": [expense.to_sheet_values()]},
            )
            .execute()
        )
        return cast(dict[str, Any], result)

    async def search(self, query: ExpenseQuery) -> list[SheetRecord]:
        return await asyncio.to_thread(self._search_sync, query)

    def _search_sync(self, query: ExpenseQuery) -> list[SheetRecord]:
        worksheets = [query.month] if query.month else self._month_worksheets_sync()
        records: list[SheetRecord] = []
        for worksheet in worksheets:
            response = (
                self._service.spreadsheets()
                .values()
                .get(
                    spreadsheetId=self._spreadsheet_id,
                    range=f"'{worksheet}'!A:G",
                    valueRenderOption="UNFORMATTED_VALUE",
                    dateTimeRenderOption="SERIAL_NUMBER",
                )
                .execute()
            )
            values = response.get("values", [])
            if values and values[0][:7] != EXPECTED_HEADERS:
                raise ValueError(f"Unexpected headers in worksheet {worksheet}")
            for row_number, values_row in enumerate(values[1:], start=2):
                expense = _parse_sheet_row(values_row)
                if expense is not None and row_matches(expense, query):
                    records.append(
                        SheetRecord(worksheet=worksheet, row_number=row_number, expense=expense)
                    )
        return records

    def _month_worksheets_sync(self) -> list[str]:
        response = (
            self._service.spreadsheets()
            .get(spreadsheetId=self._spreadsheet_id, fields="sheets.properties.title")
            .execute()
        )
        valid = {datetime(2000, month, 1).strftime("%B") for month in range(1, 13)}
        return [
            sheet["properties"]["title"]
            for sheet in response.get("sheets", [])
            if sheet["properties"]["title"] in valid
        ]

    async def update(self, record: SheetRecord, patch: ExpensePatch) -> SheetRecord:
        updated = patch.apply(record.expense)
        if updated.worksheet != record.worksheet:
            raise ValueError("Cross-month date corrections are not supported")
        await asyncio.to_thread(self._update_sync, record, updated)
        return record.model_copy(update={"expense": updated})

    def _update_sync(self, record: SheetRecord, expense: ExpenseRow) -> None:
        (
            self._service.spreadsheets()
            .values()
            .update(
                spreadsheetId=self._spreadsheet_id,
                range=f"'{record.worksheet}'!A{record.row_number}:G{record.row_number}",
                valueInputOption="USER_ENTERED",
                body={"values": [expense.to_sheet_values()]},
            )
            .execute()
        )


def load_google_credentials(credentials_path: str | None = None) -> Credentials:
    """Use an explicit service-account file or fall back to keyless ADC."""
    if credentials_path:
        return cast(
            Credentials,
            service_account.Credentials.from_service_account_file(  # type: ignore[no-untyped-call]
                credentials_path, scopes=[SHEETS_SCOPE]
            ),
        )
    credentials, _ = google.auth.default(scopes=[SHEETS_SCOPE])
    return credentials


def _row_number_from_range(updated_range: str) -> int:
    try:
        cell_range = updated_range.rsplit("!", maxsplit=1)[1]
        return int(
            "".join(character for character in cell_range.split(":")[0] if character.isdigit())
        )
    except (IndexError, ValueError) as error:
        raise ValueError(f"Unable to determine appended row from {updated_range!r}") from error


def _parse_sheet_row(values: Sequence[Any]) -> ExpenseRow | None:
    padded = [*values, *([""] * (7 - len(values)))]
    if not any(str(value).strip() for value in padded[:7]):
        return None
    try:
        cost = Decimal(str(padded[2]).replace("$", "").replace(",", ""))
    except InvalidOperation as error:
        raise ValueError(f"Invalid cost value {padded[2]!r}") from error
    return ExpenseRow.model_validate(
        {
            "Date": _parse_sheet_date(padded[0]),
            "Expense": padded[1],
            "Cost": cost,
            "Paid By": padded[3],
            "Settled": padded[4] or "N",
            "Category": padded[5],
            "Notes": padded[6],
        }
    )


def _parse_sheet_date(value: Any) -> date:
    """Parse either a Google Sheets date serial or an explicit US date string."""
    if isinstance(value, int | float) and not isinstance(value, bool):
        return date(1899, 12, 30) + timedelta(days=int(value))
    try:
        return datetime.strptime(str(value).strip(), "%m/%d/%Y").date()
    except ValueError as error:
        raise ValueError(f"Invalid date value {value!r}") from error
