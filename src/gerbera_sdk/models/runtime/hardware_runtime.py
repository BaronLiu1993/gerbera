from dataclasses import asdict, dataclass, field
from typing import Any

from gerbera_sdk.models.hardware.hardware_plan import StateKey


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
        self.state_store[key] = state

    def get_state_store(self) -> dict[str, Any]:
        return {
            self.state_key_label(key): (
                asdict(value) if value is not None else None
            )
            for key, value in self.state_store.items()
        }

    @staticmethod
    def state_key_label(key: StateKey) -> str:
        return ".".join(key)
