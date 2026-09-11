from unittest.mock import Mock

from google.auth.credentials import AnonymousCredentials

from expenses_agent.config import Settings
from expenses_agent.integrations import google_sheets
from expenses_agent.integrations.factory import build_sheets_gateway
from expenses_agent.integrations.google_sheets import SHEETS_SCOPE, GoogleSheetsGateway


def test_google_credentials_default_to_adc(mocker) -> None:
    credentials = AnonymousCredentials()
    default = mocker.patch.object(
        google_sheets.google.auth, "default", return_value=(credentials, "project-id")
    )

    assert google_sheets.load_google_credentials() is credentials
    default.assert_called_once_with(scopes=[SHEETS_SCOPE])


def test_explicit_service_account_file_remains_supported(mocker) -> None:
    credentials = AnonymousCredentials()
    from_file = mocker.patch.object(
        google_sheets.service_account.Credentials,
        "from_service_account_file",
        return_value=credentials,
    )

    assert google_sheets.load_google_credentials("/secure/credentials.json") is credentials
    from_file.assert_called_once_with("/secure/credentials.json", scopes=[SHEETS_SCOPE])


def test_factory_only_requires_spreadsheet_id_for_adc(mocker) -> None:
    constructor = mocker.patch(
        "expenses_agent.integrations.factory.GoogleSheetsGateway",
        return_value=Mock(spec=GoogleSheetsGateway),
    )
    settings = Settings(
        _env_file=None,
        sheets_backend="google",
        google_application_credentials=None,
        google_sheets_spreadsheet_id="spreadsheet-id",
    )

    build_sheets_gateway(settings)

    constructor.assert_called_once_with(None, "spreadsheet-id")
