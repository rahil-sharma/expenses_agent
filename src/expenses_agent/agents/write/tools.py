from __future__ import annotations

from expenses_agent.domain import ExpensePatch, ExpenseQuery, ExpenseRow, SheetRecord
from expenses_agent.integrations.google_sheets import SheetsGateway


class WriteTools:
    """The only Sheets capabilities exposed to the write agent."""

    def __init__(self, sheets: SheetsGateway) -> None:
        self._sheets = sheets

    async def append_expense(self, expense: ExpenseRow) -> SheetRecord:
        return await self._sheets.append(expense)

    async def find_update_candidates(self, query: ExpenseQuery) -> list[SheetRecord]:
        return await self._sheets.search(query)

    async def update_expense(self, record: SheetRecord, patch: ExpensePatch) -> SheetRecord:
        return await self._sheets.update(record, patch)
