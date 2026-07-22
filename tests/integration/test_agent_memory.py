import json
import sqlite3

from gerbera_sdk.harness.agent.agent import Agent
from gerbera_sdk.harness.agent.experiments.session import Session
from gerbera_sdk.harness.agent.experiments.states import LoopStateEnum
from gerbera_sdk.harness.memory.memory import Memory, SCHEMA_PATH


class FakeClient:
    def __init__(self) -> None:
        self.contexts = []
        self.responses = iter(
            [
                (
                    "plan",
                    {
                        "hypothesis": "Heating increases temperature.",
                        "dependent_variables": ["temperature"],
                        "independent_variables": ["heater_state"],
                        "controlled_variables": ["room_temperature"],
                        "assumptions": ["The sensor is calibrated."],
                        "methods": [],
                    },
                ),
                ("execution", "first task scoped"),
                ("observation", "first plan step executed"),
                ("review", "observations recorded"),
                ("complete", "hypothesis accepted"),
            ]
        )

    def send(
        self,
        messages: list[dict],
        system_prompt: str,
        valid_schema: dict,
    ) -> str:
        self.contexts.append(messages)
        next_state, response = next(self.responses)
        next_state_schema = valid_schema["properties"]["next_state"]
        assert next_state == next_state_schema.get("const", next_state)
        if "enum" in next_state_schema:
            assert next_state in next_state_schema["enum"]
        return json.dumps(
            {
                "next_state": next_state,
                "response": response,
            }
        )


class FakeModel:
    def __init__(self) -> None:
        self.client = FakeClient()

    def get_agent_client(self) -> FakeClient:
        return self.client


def test_agent_persists_each_accepted_state_response(tmp_path) -> None:
    connection = sqlite3.connect(tmp_path / "memory.db")
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA_PATH.read_text())
    memory = Memory(connection)
    session = Session()
    model = FakeModel()
    initial_messages = [{"role": "user", "content": "Test the sensor"}]
    agent = Agent(
        session=session,
        model=model,
        memory=memory,
        messages=initial_messages,
    )

    agent.run_agent()

    rows = connection.execute(
        "SELECT state, payload, aggregate_id FROM events_log ORDER BY timestamp"
    ).fetchall()
    assert [row["state"] for row in rows] == [
        "initialisation",
        "plan",
        "execution",
        "observation",
        "review",
    ]
    assert all(row["aggregate_id"] == session.id for row in rows)
    assert json.loads(rows[-1]["payload"]) == {
        "next_state": "complete",
        "response": "hypothesis accepted",
    }
    assert session.state.state == LoopStateEnum.COMPLETE
    assert [len(context) for context in model.client.contexts] == [1, 2, 3, 4, 5]
    assert all(
        context[0] == initial_messages[0]
        for context in model.client.contexts
    )
    assert json.loads(model.client.contexts[-1][-1]["content"]) == {
        "state": "observation",
        "next_state": "review",
        "response": "observations recorded",
    }

    connection.close()
