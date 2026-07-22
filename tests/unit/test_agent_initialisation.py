import asyncio

from gerbera_sdk.harness.agent.agent import Agent
from gerbera_sdk.harness.agent.experiments.session import Session


class FakeInitialisationProcess:
    async def run(self, user_prompt: str) -> str:
        return f"# Experiment Context\n\n## Objective\n\n{user_prompt}"


def test_agent_prepares_initialisation_context_without_transitioning() -> None:
    session = Session()
    initial_state = session.state
    agent = Agent(
        session=session,
        model=object(),
        memory=object(),
        initialisation_process=FakeInitialisationProcess(),
    )

    context = asyncio.run(
        agent.prepare_initialisation_context("Test the heater.")
    )

    assert "Test the heater." in context
    assert agent.messages == [{"role": "user", "content": context}]
    assert session.state is initial_state
