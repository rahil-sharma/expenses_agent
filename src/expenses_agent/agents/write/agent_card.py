from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill


def build_agent_card(base_url: str = "http://127.0.0.1:8002") -> AgentCard:
    return AgentCard(
        name="Expense Write Agent",
        description="Adds and safely updates monthly expense worksheet rows.",
        version="0.1.0",
        supported_interfaces=[
            AgentInterface(
                url=f"{base_url.rstrip('/')}/",
                protocol_binding="JSONRPC",
                protocol_version="1.0",
            )
        ],
        capabilities=AgentCapabilities(streaming=False, push_notifications=False),
        default_input_modes=["application/json"],
        default_output_modes=["application/json"],
        skills=[
            AgentSkill(
                id="expenses.write",
                name="Write expenses",
                description="Add expenses and update one unambiguous matching row.",
                tags=["expenses", "google-sheets", "write"],
                examples=["I spent $42.18 at Trader Joe's."],
                input_modes=["application/json"],
                output_modes=["application/json"],
            )
        ],
    )
