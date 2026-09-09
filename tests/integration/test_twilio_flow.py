from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator

from expenses_agent.config import Settings
from expenses_agent.domain import AgentRequest, AgentResult, ResultStatus
from expenses_agent.orchestrator.app import create_app
from expenses_agent.orchestrator.graph import build_supervisor_graph


class FakeAgentClient:
    def __init__(self, message: str) -> None:
        self.message = message
        self.calls: list[AgentRequest] = []

    async def call(self, request: AgentRequest) -> AgentResult:
        self.calls.append(request)
        return AgentResult(status=ResultStatus.SUCCESS, message=self.message)


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "model_backend": "stub",
        "twilio_validate_signatures": False,
        "authorized_sender_rahil": "+19802138727",
        "authorized_sender_karishma": "+19195939716",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_compound_sms_routes_write_before_read_and_deduplicates() -> None:
    configured = settings()
    write_client = FakeAgentClient("Expense added.")
    read_client = FakeAgentClient("September total is $42.18.")
    graph = build_supervisor_graph(
        settings=configured, read_client=read_client, write_client=write_client
    )
    app = create_app(settings=configured, supervisor_graph=graph)
    client = TestClient(app)
    payload = {
        "MessageSid": "SM123",
        "From": "+19802138727",
        "To": "+19195550100",
        "Body": "Log $42.18 at Trader Joe's and show my total",
    }

    first = client.post("/webhooks/twilio/sms", data=payload)
    second = client.post("/webhooks/twilio/sms", data=payload)

    assert first.status_code == 200
    assert first.text == second.text
    assert "Expense added." in first.text
    assert "September total" in first.text
    assert len(write_client.calls) == len(read_client.calls) == 1
    assert write_client.calls[0].default_payer == "Rahil"


def test_rejects_unauthorized_sender() -> None:
    app = create_app(settings=settings())
    response = TestClient(app).post(
        "/webhooks/twilio/sms",
        data={
            "MessageSid": "SM999",
            "From": "+19195559999",
            "To": "+19195550100",
            "Body": "Show total",
        },
    )
    assert response.status_code == 403


def test_twilio_signature_validation() -> None:
    configured = settings(twilio_validate_signatures=True, twilio_auth_token="secret")
    read_client = FakeAgentClient("No expenses found.")
    graph = build_supervisor_graph(
        settings=configured,
        read_client=read_client,
        write_client=FakeAgentClient("Expense added."),
    )
    app = create_app(settings=configured, supervisor_graph=graph)
    client = TestClient(app)
    url = "http://testserver/webhooks/twilio/sms"
    payload = {
        "MessageSid": "SM-SIGNED",
        "From": "+19802138727",
        "To": "+19195550100",
        "Body": "Show total",
    }
    signature = RequestValidator("secret").compute_signature(url, payload)

    invalid = client.post(url, data=payload, headers={"X-Twilio-Signature": "bad"})
    assert invalid.status_code == 403

    valid = client.post(url, data=payload, headers={"X-Twilio-Signature": signature})
    assert valid.status_code == 200
    assert "No expenses found." in valid.text
    assert len(read_client.calls) == 1
