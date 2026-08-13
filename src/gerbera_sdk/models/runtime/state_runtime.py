from dataclasses import asdict, dataclass, field
import json


@dataclass
class ConnectionState:
    value: str
    unit: str


@dataclass
class StateRuntime:
    # Store the device_name and the component_name
    state_store: dict[tuple[str, str], ConnectionState | None] = field(
        default_factory=dict
    )

    def register_state_store(self, connection_name: str, component_type: str) -> None:
        state_key = (connection_name, component_type)
        if state_key in self.state_store:
            raise KeyError("Key Already Exists")
        self.state_store[state_key] = None

    def update_state(
        self,
        connection_name: str,
        component_type: str,
        state: ConnectionState,
    ) -> None:
        self.state_store[(connection_name, component_type)] = state

    def get_state_store(self):
        serializable = {
            f"{conn}::{comp}": asdict(value) if value is not None else None
            for (conn, comp), value in self.state_store.items()
        }
        return json.dumps(serializable)
