from dataclasses import dataclass, field
from typing import Any
import uuid

from gerbera_sdk.contracts.firmware_contract import OutputEventType
from gerbera_sdk.models.database import Database
from gerbera_sdk.models.microcontroller import Microcontroller
from gerbera_sdk.firmware.configurations import MICROCONTROLLER_MAPPING
from gerbera_sdk.firmware.configurations import DEVICES_MAPPING
from gerbera_sdk.rule_engine.rule_buffer import RuleBuffer
from gerbera_sdk.rule_engine.rule_bus import RuleBus
from gerbera_sdk.rule_engine.rule_group import RuleGroup


@dataclass
class HardwareSystem:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    microcontrollers: list[Microcontroller] = field(default_factory=list)
    database: Database | None = None
    rule_groups: list[RuleGroup] = field(default_factory=list)
    rule_bus: RuleBus = field(default_factory=RuleBus)
    rule_buffer: RuleBuffer = field(init=False)

    def __post_init__(self) -> None:
        self.rule_buffer = RuleBuffer(rule_bus=self.rule_bus)

        if self.database is not None and not self.database.hardware_system_id:
            self.database.hardware_system_id = self.id

        if self.microcontrollers:
            microcontrollers = list(self.microcontrollers)
            self.microcontrollers = []
            self.add_microcontrollers(microcontrollers)

        if self.rule_groups:
            rule_groups = list(self.rule_groups)
            self.rule_groups = []
            self.add_rule_groups(rule_groups)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "microcontrollers": [
                microcontroller.to_dict()
                for microcontroller in self.microcontrollers
            ],
            "database": self.database.to_dict() if self.database is not None else None,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "HardwareSystem":
        return cls(
            id=str(payload["id"]),
            description=str(payload.get("description", "")),
            microcontrollers=[
                Microcontroller.from_dict(microcontroller)
                for microcontroller in payload.get("microcontrollers", [])
            ],
            database=(
                Database.from_dict(payload["database"])
                if payload.get("database") is not None
                else None
            ),
        )

    # For now have it dedupe like this but i dont think this is a good way to dedupe
    def add_rule_groups(self, rule_groups: list[RuleGroup]) -> None:
        existing_rule_group_ids = {
            rule_group.id for rule_group in self.rule_groups
        }

        for rule_group in rule_groups:
            self._prepare_rule_group(rule_group)

            if rule_group.id in existing_rule_group_ids:
                raise ValueError(
                    f"Rule group already exists in hardware system {self.id}: "
                    f"{rule_group.id}"
                )

            existing_rule_group_ids.add(rule_group.id)
            self.rule_groups.append(rule_group)
    
    # Add All Microcontrollers at Once to The List
    def add_microcontrollers(self, microcontrollers: list[Microcontroller]) -> None:
        existing_microcontroller_ids = {
            microcontroller.id for microcontroller in self.microcontrollers
        }

        for microcontroller in microcontrollers:
            self._prepare_microcontroller(microcontroller)

            if microcontroller.id in existing_microcontroller_ids:
                raise ValueError(
                    f"Microcontroller already exists in hardware system {self.id}: "
                    f"{microcontroller.id}"
                )

            existing_microcontroller_ids.add(microcontroller.id)
            self.microcontrollers.append(microcontroller)

    def _prepare_microcontroller(self, microcontroller: Microcontroller) -> None:
        if not microcontroller.hardware_system_id:
            microcontroller.hardware_system_id = self.id

        if microcontroller.hardware_system_id != self.id:
            raise ValueError(
                f"Microcontroller {microcontroller.id} belongs to hardware system "
                f"{microcontroller.hardware_system_id}, expected {self.id}"
            )

        if microcontroller.database is None and self.database is not None:
            from gerbera_sdk.firmware.configurations import DEVICES_MAPPING

            supports_database = any(
                connection.component_type in DEVICES_MAPPING
                and DEVICES_MAPPING[connection.component_type]().supports_database
                for connection in microcontroller.connections
            )
            if supports_database:
                microcontroller.database = self.database

        if microcontroller.connections:
            connections = list(microcontroller.connections)
            microcontroller.connections = []
            microcontroller.add_connections(connections)

    def _prepare_rule_group(self, rule_group: RuleGroup) -> None:
        if not rule_group.conditions:
            raise ValueError("RuleGroup must contain at least one condition")

        rule_group.rule_buffer = self.rule_buffer

        for condition in rule_group.conditions:
            connection = self._find_connection_for_condition(
                microcontroller_id=condition.microcontroller_id,
                event_name=condition.event_name,
            )
            self._validate_condition_against_connection(condition, connection)
            self._register_condition_with_runtime(condition, rule_group, connection)

    def _find_connection_for_condition(
        self,
        microcontroller_id: str,
        event_name: str,
    ):
        for microcontroller in self.microcontrollers:
            if microcontroller.id != microcontroller_id:
                continue

            for connection in microcontroller.connections:
                if connection.event_name == event_name:
                    return connection

        raise ValueError(
            f"No connection found in hardware system {self.id} for "
            f"microcontroller_id={microcontroller_id!r}, event_name={event_name!r}"
        )

    def _validate_condition_against_connection(self, condition, connection) -> None:
        if connection.component_type not in DEVICES_MAPPING:
            raise ValueError(
                f"Unsupported component type for rule registration: "
                f"{connection.component_type}"
            )

        builder = DEVICES_MAPPING[connection.component_type]()
        output_contract = builder.output_contract(connection)
        normalized_event_type = OutputEventType(condition.event_type)
        valid_fields = output_contract.get(normalized_event_type, {})

        if condition.field_name not in valid_fields:
            raise ValueError(
                f"Field {condition.field_name!r} is not valid for "
                f"{normalized_event_type.value} on {connection.component_type}. "
                f"Valid fields: {sorted(valid_fields.keys())}"
            )

    def _register_condition_with_runtime(
        self,
        condition,
        rule_group: RuleGroup,
        connection,
    ) -> None:
        builder = DEVICES_MAPPING[connection.component_type]()
        output_contract = builder.output_contract(connection)
        normalized_event_type = OutputEventType(condition.event_type)
        event_fields = output_contract.get(normalized_event_type, {})
        condition_field_name = condition.field_name

        self.rule_buffer.register_event_in_buffer(
            condition.event_type,
            condition.microcontroller_id,
            condition.event_name,
            schema=(
                {condition_field_name: event_fields[condition_field_name]}
                if condition_field_name in event_fields
                else {}
            ),
        )
        self.rule_bus.register_rule_group(
            condition.event_type,
            condition.microcontroller_id,
            condition.event_name,
            rule_group,
        )
    
    def get_required_microcontroller_packages(self) -> list[str]:
        libraries: list[str] = []
        normalized_library_names: set[str] = set()

        for microcontroller in self.microcontrollers:
            fqbn = microcontroller.fqbn
            if fqbn not in MICROCONTROLLER_MAPPING:
                raise ValueError(f"Unsupported microcontroller fqbn: {fqbn}")

            package_names = MICROCONTROLLER_MAPPING[fqbn]["libraries"]

            for library in package_names:
                normalized_library = library.strip().lower()
                if normalized_library in normalized_library_names:
                    continue

                libraries.append(library)
                normalized_library_names.add(normalized_library)

        return libraries
