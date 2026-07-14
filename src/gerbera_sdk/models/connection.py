from dataclasses import dataclass, field
from typing import Any, Callable, Optional
import uuid

from gerbera_sdk.contracts.firmware_contract import OutputEventType
from gerbera_sdk.events.event_worker import event_worker
from gerbera_sdk.models.database import Database
from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event import Event
from gerbera_sdk.events.utils import build_connection_event_name
from gerbera_sdk.firmware.configurations import DEVICES_MAPPING
from gerbera_sdk.rule_engine.rule_buffer import RuleBuffer
from gerbera_sdk.rule_engine.condition import Condition, OperatorEnum




@dataclass
class Connection:
    name: str
    component_type: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    microcontroller_id: str = ""
    hardware_system_id: str = ""
    pins: Optional[dict[str, str]] = None
    description: str = ""
    database: Database | None = None
    event_bus: EventBus | None = None
    rule_buffer: RuleBuffer | None = None
    actions: dict[
        str,
        Callable[[Optional[dict[str, str]]], dict[str, str]],
    ] = field(default_factory=dict, repr=False)

    @property
    def event_name(self) -> str:
        return build_connection_event_name(
            component_type=self.component_type,
            microcontroller_id=self.microcontroller_id,
        )

    def __post_init__(self) -> None:
        if self.event_bus is None:
            return

        if self.component_type not in DEVICES_MAPPING:
            raise ValueError(
                f"Unsupported component type for event registration: "
                f"{self.component_type}"
            )

        builder = DEVICES_MAPPING[self.component_type]()

        if self.database is not None:
            if not builder.supports_database:
                raise ValueError(
                    f"{self.component_type} does not support database streaming"
                )

            event_worker.configure_database(self.database)
            event_worker.start()

            schema = builder.required_schema(self)
            table_name = self.event_name
            self.database.create_database_table(table_name, schema)
            self._register_stream_event(table_name)

        self._register_mcp_event()

    def _register_stream_event(self, table_name: str) -> None:
        event_type = "STREAM"
        event_name = self.event_name
        builder = DEVICES_MAPPING[self.component_type]()

        event = Event(
            event_type=event_type,
            microcontroller_id=self.microcontroller_id,
            event_name=event_name,
            streamable=True,
            table_name=table_name,
        )
        self.event_bus.add_event(
            event_type,
            self.microcontroller_id,
            event_name,
            event,
        )

        if self.rule_buffer is not None:
            self.rule_buffer.register_event_in_buffer(
                event_type,
                self.microcontroller_id,
                event_name,
                schema=builder.required_schema(self),
            )

    def _register_mcp_event(self) -> None:
        event_type = "MCP"
        event_name = self.event_name
        event = Event(
            event_type=event_type,
            microcontroller_id=self.microcontroller_id,
            event_name=event_name,
        )
        self.event_bus.add_event(
            event_type,
            self.microcontroller_id,
            event_name,
            event,
        )

        if self.rule_buffer is not None:
            self.rule_buffer.register_event_in_buffer(
                event_type,
                self.microcontroller_id,
                event_name,
            )

    def register_action(
        self,
        action: str,
        callback: Callable[[Optional[dict[str, str]]], dict[str, str]],
    ) -> None:
        self.actions[action.strip().upper()] = callback

    def create_condition(
        self,
        field_name: str,
        operator: OperatorEnum,
        expected: str,
        event_type: OutputEventType | str | None = None,
    ) -> Condition:

        builder = DEVICES_MAPPING[self.component_type]()
        output_contract = builder.output_contract(self)

        normalized_field_name = str(field_name)
        resolved_event_type = self._resolve_condition_event_type(
            output_contract=output_contract,
            field_name=normalized_field_name,
            event_type=event_type,
        )

        normalized_operator = (
            operator
            if isinstance(operator, OperatorEnum)
            else OperatorEnum(str(operator))
        )

        return Condition(
            event_type=resolved_event_type.value,
            microcontroller_id=self.microcontroller_id,
            event_name=self.event_name,
            field_name=normalized_field_name,
            expected=str(expected),
            operator=normalized_operator,
        )

    def perform_action(
        self,
        action: str,
        params: Optional[dict[str, str]] = None,
    ) -> dict[str, str]:
        normalized_action = action.strip().upper()
        if normalized_action not in self.actions:
            raise RuntimeError(
                f"Action is not registered for {self.name}: {normalized_action}"
            )

        return self.actions[normalized_action](params)

    def _resolve_condition_event_type(
        self,
        output_contract: dict[OutputEventType, dict[str, Any]],
        field_name: str,
        event_type: OutputEventType | str | None,
    ) -> OutputEventType:
        if event_type is None:
            valid_fields = sorted(
                {
                    output_field_name
                    for fields in output_contract.values()
                    for output_field_name in fields.keys()
                }
            )
            raise ValueError(
                f"event_type is required when creating a condition for "
                f"{self.component_type}. Valid fields: {valid_fields}"
            )

        normalized_event_type = (
            event_type
            if isinstance(event_type, OutputEventType)
            else OutputEventType(str(event_type))
        )
        fields = output_contract.get(normalized_event_type, {})
        if field_name not in fields:
            valid_fields = sorted(fields.keys())
            raise ValueError(
                f"Field {field_name!r} is not available for "
                f"{normalized_event_type.value} on {self.component_type}. "
                f"Valid fields: {valid_fields}"
            )

        return normalized_event_type

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "hardware_system_id": self.hardware_system_id,
            "microcontroller_id": self.microcontroller_id,
            "name": self.name,
            "description": self.description,
            "component_type": self.component_type,
            "pins": dict(self.pins or {}),
            "database": self.database.to_dict() if self.database is not None else None,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Connection":
        return cls(
            id=str(payload.get("id", "")),
            hardware_system_id=str(payload.get("hardware_system_id", "")),
            microcontroller_id=str(payload.get("microcontroller_id", "")),
            name=str(payload.get("name", "")),
            component_type=str(payload.get("component_type", "")),
            pins={
                str(pin_name): str(pin_value)
                for pin_name, pin_value in payload.get("pins", {}).items()
            },
            description=str(payload.get("description", "")),
            database=(
                Database.from_dict(payload["database"])
                if payload.get("database") is not None
                else None
            ),
        )
