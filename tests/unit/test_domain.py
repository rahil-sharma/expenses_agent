from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from expenses_agent.domain import ExpenseCategory, ExpenseRow, PaidBy, Settled
from expenses_agent.domain.requests import normalize_us_phone


def test_expense_row_matches_sheet_contract() -> None:
    expense = ExpenseRow(
        Date=date(2026, 9, 9),
        Expense="Trader Joe's",
        Cost="$42.18",
        **{"Paid By": "Rahil", "Category": "Groceries"},
    )

    assert expense.cost == Decimal("42.18")
    assert expense.settled is Settled.NO
    assert expense.worksheet == "September"
    assert expense.to_sheet_values() == [
        "09/09/2026",
        "Trader Joe's",
        42.18,
        "Rahil",
        "N",
        "Groceries",
        "",
    ]


@pytest.mark.parametrize("number", ["9802138727", "(980) 213-8727", "+1 980 213 8727"])
def test_normalize_us_phone(number: str) -> None:
    assert normalize_us_phone(number) == "+19802138727"


def test_expense_enums_are_closed() -> None:
    with pytest.raises(ValidationError):
        ExpenseRow(
            date=date.today(),
            expense="Unknown",
            cost="10",
            paid_by="Someone Else",
            category="Entertainment",
        )

    assert set(PaidBy) == {PaidBy.RAHIL, PaidBy.KARISHMA}
    assert len(ExpenseCategory) == 5
