from __future__ import annotations

from datetime import date as Date
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PaidBy(StrEnum):
    RAHIL = "Rahil"
    KARISHMA = "Karishma"


class Settled(StrEnum):
    YES = "Y"
    NO = "N"


class ExpenseCategory(StrEnum):
    MISC = "Misc"
    TRANSPORTATION = "Transportation"
    RENT = "Rent"
    FOOD_DRINKS = "Food / Drinks"
    GROCERIES = "Groceries"


class ExpenseRow(BaseModel):
    """Validated representation of the seven columns in every monthly tab."""

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    date: Date = Field(alias="Date")
    expense: str = Field(alias="Expense", min_length=1)
    cost: Decimal = Field(alias="Cost", gt=0, max_digits=12, decimal_places=2)
    paid_by: PaidBy = Field(alias="Paid By")
    settled: Settled = Field(default=Settled.NO, alias="Settled")
    category: ExpenseCategory = Field(alias="Category")
    notes: str = Field(default="", alias="Notes")

    @field_validator("cost", mode="before")
    @classmethod
    def clean_cost(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().replace("$", "").replace(",", "")
        return value

    @property
    def worksheet(self) -> str:
        return self.date.strftime("%B")

    def to_sheet_values(self) -> list[str | float]:
        return [
            self.date.strftime("%m/%d/%Y"),
            self.expense,
            float(self.cost),
            self.paid_by.value,
            self.settled.value,
            self.category.value,
            self.notes,
        ]


class ExpensePatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    date: Date | None = None
    expense: str | None = Field(default=None, min_length=1)
    cost: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    paid_by: PaidBy | None = None
    settled: Settled | None = None
    category: ExpenseCategory | None = None
    notes: str | None = None

    @field_validator("cost", mode="before")
    @classmethod
    def clean_cost(cls, value: Any) -> Any:
        return ExpenseRow.clean_cost(value)

    def apply(self, expense: ExpenseRow) -> ExpenseRow:
        return expense.model_copy(update=self.model_dump(exclude_none=True))


class ExpenseQuery(BaseModel):
    month: str | None = None
    start_date: Date | None = None
    end_date: Date | None = None
    expense_contains: str | None = None
    cost: Decimal | None = None
    paid_by: PaidBy | None = None
    settled: Settled | None = None
    category: ExpenseCategory | None = None

    @field_validator("month")
    @classmethod
    def validate_month(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = value.strip().title()
        months = {Date(2000, month, 1).strftime("%B") for month in range(1, 13)}
        if candidate not in months:
            raise ValueError("month must be a full English month name")
        return candidate


class SheetRecord(BaseModel):
    worksheet: str
    row_number: int = Field(ge=2)
    expense: ExpenseRow
