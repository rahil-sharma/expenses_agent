from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response, status
from langgraph.graph.state import CompiledStateGraph

from expenses_agent.config import Settings, get_settings
from expenses_agent.domain import InboundSMS
from expenses_agent.integrations.idempotency import IdempotencyStore, InMemoryIdempotencyStore
from expenses_agent.integrations.twilio import twiml_message, validate_twilio_request
from expenses_agent.orchestrator.graph import graph
from expenses_agent.orchestrator.state import SupervisorState


def create_app(
    *,
    settings: Settings | None = None,
    supervisor_graph: CompiledStateGraph[Any, Any, Any, Any] | None = None,
    idempotency_store: IdempotencyStore | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_graph = supervisor_graph or graph
    store = idempotency_store or InMemoryIdempotencyStore()
    app = FastAPI(title="Expense SMS Orchestrator", version="0.1.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "orchestrator"}

    @app.post("/webhooks/twilio/sms")
    async def inbound_sms(request: Request) -> Response:
        form = await request.form()
        params = {key: str(value) for key, value in form.items()}
        if resolved_settings.twilio_validate_signatures:
            if resolved_settings.twilio_auth_token is None:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Twilio validation is enabled but no auth token is configured",
                )
            signature = request.headers.get("X-Twilio-Signature", "")
            if not validate_twilio_request(
                url=str(request.url),
                params=params,
                signature=signature,
                auth_token=resolved_settings.twilio_auth_token.get_secret_value(),
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature"
                )

        message = InboundSMS(
            message_sid=params.get("MessageSid", ""),
            from_number=params.get("From", ""),
            to_number=params.get("To", ""),
            body=params.get("Body", ""),
            received_at=datetime.now(resolved_settings.zoneinfo),
        )
        payer = resolved_settings.sender_payer_map.get(message.from_number)
        if payer is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Sender not authorized"
            )

        cached = await store.get(message.message_sid)
        if cached is not None:
            return Response(content=cached, media_type="application/xml")

        output = await resolved_graph.ainvoke({"sms": message, "default_payer": payer})
        state = SupervisorState.model_validate(output)
        xml = twiml_message(state.response_text or "I couldn't process that request.")
        await store.put(message.message_sid, xml)
        return Response(content=xml, media_type="application/xml")

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("expenses_agent.orchestrator.app:app", host="127.0.0.1", port=8000, reload=False)
