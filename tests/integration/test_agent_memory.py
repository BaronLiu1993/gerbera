import json
import sqlite3

from gerbera_sdk.harness.agent.agent import Agent
from gerbera_sdk.harness.agent.experiments.session import Session
from gerbera_sdk.harness.agent.experiments.states import LoopStateEnum
from gerbera_sdk.harness.memory.memory import Memory, SCHEMA_PATH


class FakeClient:
    def __init__(self) -> None:
        self.responses = iter(
            [
                ("plan", "hypothesis generated"),
                ("execute", "plan generated"),
                ("observe", "plan executed"),
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
        next_state, response = next(self.responses)
        assert next_state in valid_schema["properties"]["next_state"]["enum"]
        return json.dumps(
            {
                "next_state": next_state,
                "response": response,
            }
        )


class FakeModel:
    def get_agent_client(self) -> FakeClient:
        return FakeClient()


def test_agent_persists_each_accepted_state_response(tmp_path) -> None:
    connection = sqlite3.connect(tmp_path / "memory.db")
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA_PATH.read_text())
    memory = Memory(connection)
    session = Session()
    agent = Agent(session=session, model=FakeModel(), memory=memory)

    agent.run_agent([])

    rows = connection.execute(
        "SELECT state, payload, aggregate_id FROM events_log ORDER BY timestamp"
    ).fetchall()
    assert [row["state"] for row in rows] == [
        "hypothesize",
        "plan",
        "execute",
        "observe",
        "review",
    ]
    assert all(row["aggregate_id"] == session.id for row in rows)
    assert json.loads(rows[-1]["payload"]) == {
        "next_state": "complete",
        "response": "hypothesis accepted",
    }
    assert session.state.state == LoopStateEnum.COMPLETE

    connection.close()
