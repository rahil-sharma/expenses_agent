from __future__ import annotations

import asyncio
from collections import defaultdict

from expenses_agent.domain.expenses import ExpensePatch, ExpenseQuery, ExpenseRow, SheetRecord
from expenses_agent.integrations.google_sheets import EXPECTED_HEADERS, row_matches


class FakeSheetsGateway:
    """Concurrency-safe in-memory adapter for local development and tests."""

    def __init__(self, seed: list[ExpenseRow] | None = None) -> None:
        self._rows: dict[str, list[ExpenseRow]] = defaultdict(list)
        self._lock = asyncio.Lock()
        for expense in seed or []:
            self._rows[expense.worksheet].append(expense)

    async def append(self, expense: ExpenseRow) -> SheetRecord:
        async with self._lock:
            rows = self._rows[expense.worksheet]
            rows.append(expense)
            return SheetRecord(
                worksheet=expense.worksheet,
                row_number=len(rows) + 1,
                expense=expense,
            )

    async def search(self, query: ExpenseQuery) -> list[SheetRecord]:
        async with self._lock:
            records: list[SheetRecord] = []
            for worksheet, expenses in self._rows.items():
                for row_number, expense in enumerate(expenses, start=2):
                    if row_matches(expense, query):
                        records.append(
                            SheetRecord(
                                worksheet=worksheet,
                                row_number=row_number,
                                expense=expense,
                            )
                        )
            return records

    async def update(self, record: SheetRecord, patch: ExpensePatch) -> SheetRecord:
        async with self._lock:
            index = record.row_number - 2
            rows = self._rows[record.worksheet]
            if index < 0 or index >= len(rows):
                raise LookupError("Expense row no longer exists")
            updated = patch.apply(rows[index])
            if updated.worksheet != record.worksheet:
                raise ValueError("Cross-month date corrections are not supported")
            rows[index] = updated
            return record.model_copy(update={"expense": updated})

    async def raw_values(self, worksheet: str) -> list[list[str | float]]:
        async with self._lock:
            headers: list[str | float] = list(EXPECTED_HEADERS)
            return [headers, *[row.to_sheet_values() for row in self._rows[worksheet]]]
