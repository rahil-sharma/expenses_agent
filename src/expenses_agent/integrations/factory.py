from __future__ import annotations

from expenses_agent.config import Settings
from expenses_agent.integrations.fake_sheets import FakeSheetsGateway
from expenses_agent.integrations.google_sheets import GoogleSheetsGateway, SheetsGateway


def build_sheets_gateway(settings: Settings) -> SheetsGateway:
    if settings.sheets_backend == "fake":
        return FakeSheetsGateway()
    if not settings.google_sheets_spreadsheet_id:
        raise ValueError("Google Sheets requires GOOGLE_SHEETS_SPREADSHEET_ID")
    return GoogleSheetsGateway(
        settings.google_application_credentials, settings.google_sheets_spreadsheet_id
    )
