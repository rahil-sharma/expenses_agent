from datetime import date

import pytest

from expenses_agent.integrations.google_sheets import _parse_sheet_date


def test_parse_google_sheets_date_serial() -> None:
    assert _parse_sheet_date(46252) == date(2026, 8, 18)


def test_parse_explicit_us_date() -> None:
    assert _parse_sheet_date("09/10/2026") == date(2026, 9, 10)


def test_reject_invalid_date() -> None:
    with pytest.raises(ValueError, match="Invalid date value"):
        _parse_sheet_date("8/18")
