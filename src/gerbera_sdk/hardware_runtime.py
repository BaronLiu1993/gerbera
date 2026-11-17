from dataclasses import asdict, dataclass, field
from typing import Any

from gerbera_sdk.utils import StateKey

@dataclass
class ConnectionState:
    value: str
    unit: str | None = None


@dataclass
class HardwareRuntime:
    state_store: dict[StateKey, ConnectionState | None] = field(
        default_factory=dict
    )

    def register_state_store(
        self,
        key: StateKey,
    ) -> None:
        self.state_store.setdefault(key, None)

    def update_state(
        self,
        key: StateKey,
        state: ConnectionState,
    ) -> None:
        if key not in self.state_store:
            raise ValueError("Key does not exist in state store")
        self.state_store[key] = state

    def get_state_store(self) -> dict[str, Any]:
        states: dict[str, Any] = {}
        for key, value in self.state_store.items():
            label = self.state_key_label(key)
            if value is None:
                states[label] = None
            else:
                states[label] = asdict(value)
        return states

    def get_state_key_label(key: StateKey) -> str:
        return ".".join(key)
