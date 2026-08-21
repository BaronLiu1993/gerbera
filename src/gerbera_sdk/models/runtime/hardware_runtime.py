from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ConnectionState:
    value: str
    unit: str | None = None


@dataclass
class HardwareRuntime:
    # Store the component type, connection name, and state field.
    state_store: dict[tuple[str, str, str], ConnectionState | None] = field(
        default_factory=dict
    )

    def register_state_store(
        self,
        connection_name: str,
        component_type: str,
        field_name: str,
    ) -> None:
        state_key = (component_type, connection_name, field_name)
        self.state_store.setdefault(state_key, None)

    def update_state(
        self,
        connection_name: str,
        component_type: str,
        field_name: str,
        state: ConnectionState,
    ) -> None:
        self.state_store[(component_type, connection_name, field_name)] = state

    def get_state_store(self) -> dict[str, Any]:
        return {
            f"{comp}.{conn}.{field_name}": (
                asdict(value) if value is not None else None
            )
            for (comp, conn, field_name), value in self.state_store.items()
        }
