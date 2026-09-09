from __future__ import annotations

from collections.abc import Mapping

from twilio.request_validator import RequestValidator  # type: ignore[import-untyped]
from twilio.twiml.messaging_response import MessagingResponse  # type: ignore[import-untyped]


def validate_twilio_request(
    *, url: str, params: Mapping[str, str], signature: str, auth_token: str
) -> bool:
    return bool(RequestValidator(auth_token).validate(url, dict(params), signature))


def twiml_message(message: str) -> str:
    response = MessagingResponse()
    response.message(message)
    return str(response)
