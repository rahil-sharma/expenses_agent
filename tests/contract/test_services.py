import importlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from expenses_agent.agents.read.app import app as read_app
from expenses_agent.agents.write.app import app as write_app
from expenses_agent.orchestrator.app import app as orchestrator_app


def test_service_health_checks() -> None:
    services = (
        (orchestrator_app, "orchestrator"),
        (read_app, "read-agent"),
        (write_app, "write-agent"),
    )
    for app, service in services:
        response = TestClient(app).get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": service}


def test_langgraph_config_exports_importable_graphs() -> None:
    config = json.loads(Path("langgraph.json").read_text())
    assert set(config["graphs"]) == {"supervisor", "read_agent", "write_agent"}
    for target in config["graphs"].values():
        module_path, attribute = target.removeprefix("./src/").split(":")
        module = importlib.import_module(module_path.removesuffix(".py").replace("/", "."))
        assert hasattr(module, attribute)
