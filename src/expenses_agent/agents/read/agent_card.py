from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill


def build_agent_card(base_url: str = "http://127.0.0.1:8001") -> AgentCard:
    return AgentCard(
        name="Expense Read Agent",
        description="Searches and summarizes monthly expense worksheets.",
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
                id="expenses.read",
                name="Read expenses",
                description="Find, total, and group expense rows.",
                tags=["expenses", "google-sheets", "read"],
                examples=["How much did we spend on groceries in September?"],
                input_modes=["application/json"],
                output_modes=["application/json"],
            )
        ],
    )
