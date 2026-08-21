from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ConnectionState:
    value: str
    unit: str | None = None


@dataclass
class HardwareRuntime:
    state_store: dict[str, ConnectionState | None] = field(
        default_factory=dict
    )

    def register_state_store(
        self,
        key: str,
    ) -> None:
        self.state_store.setdefault(key, None)

    def update_state(
        self,
        key: str,
        state: ConnectionState,
    ) -> None:
        self.state_store[key] = state

    def get_state_store(self) -> dict[str, Any]:
        return {
            key: (
                asdict(value) if value is not None else None
            )
            for key, value in self.state_store.items()
        }
