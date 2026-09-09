from datetime import date

import pytest

from expenses_agent.domain import (
    ExpenseCategory,
    ExpensePatch,
    ExpenseQuery,
    ExpenseRow,
    PaidBy,
    Settled,
)
from expenses_agent.integrations.fake_sheets import FakeSheetsGateway


@pytest.fixture
def expense() -> ExpenseRow:
    return ExpenseRow(
        date=date(2026, 9, 9),
        expense="Trader Joe's",
        cost="42.18",
        paid_by=PaidBy.RAHIL,
        category=ExpenseCategory.GROCERIES,
    )


async def test_append_search_and_update(expense: ExpenseRow) -> None:
    sheets = FakeSheetsGateway()
    record = await sheets.append(expense)

    matches = await sheets.search(ExpenseQuery(month="September", expense_contains="trader"))
    assert matches == [record]

    updated = await sheets.update(record, ExpensePatch(settled=Settled.YES))
    assert updated.expense.settled is Settled.YES
    assert (await sheets.search(ExpenseQuery(settled=Settled.NO))) == []


async def test_cross_month_update_is_rejected(expense: ExpenseRow) -> None:
    sheets = FakeSheetsGateway([expense])
    record = (await sheets.search(ExpenseQuery()))[0]

    with pytest.raises(ValueError, match="Cross-month"):
        await sheets.update(record, ExpensePatch(date=date(2026, 10, 1)))
