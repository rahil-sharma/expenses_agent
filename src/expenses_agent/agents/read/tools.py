from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from expenses_agent.domain import ExpenseQuery, SheetRecord
from expenses_agent.integrations.google_sheets import SheetsGateway


class ReadTools:
    """Read-only capabilities exposed to the read agent."""

    def __init__(self, sheets: SheetsGateway) -> None:
        self._sheets = sheets

    async def search_expenses(self, query: ExpenseQuery) -> list[SheetRecord]:
        return await self._sheets.search(query)

    @staticmethod
    def total(records: list[SheetRecord]) -> dict[str, str]:
        value = sum((record.expense.cost for record in records), start=Decimal("0"))
        return {"total": f"{value:.2f}"}

    @staticmethod
    def group_by_category(records: list[SheetRecord]) -> dict[str, str]:
        totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for record in records:
            totals[record.expense.category.value] += record.expense.cost
        return {key: f"{value:.2f}" for key, value in sorted(totals.items())}

    @staticmethod
    def group_by_payer(records: list[SheetRecord]) -> dict[str, str]:
        totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for record in records:
            totals[record.expense.paid_by.value] += record.expense.cost
        return {key: f"{value:.2f}" for key, value in sorted(totals.items())}
