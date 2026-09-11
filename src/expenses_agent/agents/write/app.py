from __future__ import annotations

from a2a.server.agent_execution import AgentExecutor
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes.agent_card_routes import create_agent_card_routes
from a2a.server.routes.fastapi_routes import add_a2a_routes_to_fastapi
from a2a.server.routes.jsonrpc_routes import create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from fastapi import FastAPI

from expenses_agent.agents.write.agent_card import build_agent_card
from expenses_agent.agents.write.executor import build_executor


def create_app(
    base_url: str = "http://127.0.0.1:8002", executor: AgentExecutor | None = None
) -> FastAPI:
    app = FastAPI(title="Expense Write Agent", version="0.1.0")
    card = build_agent_card(base_url)
    handler = DefaultRequestHandler(executor or build_executor(), InMemoryTaskStore(), card)
    add_a2a_routes_to_fastapi(
        app,
        agent_card_routes=create_agent_card_routes(card),
        jsonrpc_routes=create_jsonrpc_routes(handler, rpc_url="/"),
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "write-agent"}

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("expenses_agent.agents.write.app:app", host="127.0.0.1", port=8002, reload=False)
