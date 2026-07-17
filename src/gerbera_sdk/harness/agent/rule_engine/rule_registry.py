from dataclasses import dataclass, field
from typing import TYPE_CHECKING
import uuid

from gerbera_sdk.contracts.firmware_contract import OutputEventType
from gerbera_sdk.firmware.configurations import DEVICES_MAPPING
from gerbera_sdk.harness.agent.rule_engine.rule_buffer import RuleBuffer
from gerbera_sdk.harness.agent.rule_engine.rule_bus import RuleBus
from gerbera_sdk.harness.agent.rule_engine.rule_group import RuleGroup

if TYPE_CHECKING:
    from gerbera_sdk.models.hardware.connection import Connection
    from gerbera_sdk.models.hardware.hardware_system import HardwareSystem


@dataclass
class RuleRegistry:
    rule_groups: list[RuleGroup] = field(default_factory=list)
    rule_bus: RuleBus = field(default_factory=RuleBus)
    rule_buffer: RuleBuffer = field(init=False)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        self.rule_buffer = RuleBuffer(rule_bus=self.rule_bus)

    def add_rule_groups(
        self,
        hardware_system: "HardwareSystem",
        rule_groups: list[RuleGroup],
    ) -> None:
        existing_rule_group_ids = {
            rule_group.id for rule_group in self.rule_groups
        }

        for rule_group in rule_groups:
            self._prepare_rule_group(hardware_system, rule_group)

            if rule_group.id in existing_rule_group_ids:
                raise ValueError(
                    f"Rule group already exists in hardware system {hardware_system.id}: "
                    f"{rule_group.id}"
                )

            existing_rule_group_ids.add(rule_group.id)
            self.rule_groups.append(rule_group)

    def _prepare_rule_group(
        self,
        hardware_system: "HardwareSystem",
        rule_group: RuleGroup,
    ) -> None:
        if not rule_group.conditions:
            raise ValueError("RuleGroup must contain at least one condition")

        rule_group.rule_buffer = self.rule_buffer

        for condition in rule_group.conditions:
            connection = self._find_connection_for_condition(
                hardware_system=hardware_system,
                microcontroller_id=condition.microcontroller_id,
                event_name=condition.event_name,
            )
            self._validate_condition_against_connection(condition, connection)
            self._register_condition_with_runtime(condition, rule_group, connection)

    def _find_connection_for_condition(
        self,
        hardware_system: "HardwareSystem",
        microcontroller_id: str,
        event_name: str,
    ) -> "Connection":
        for microcontroller in hardware_system.microcontrollers:
            if microcontroller.id != microcontroller_id:
                continue

            for connection in microcontroller.connections:
                if connection.event_name == event_name:
                    return connection

        raise ValueError(
            f"No connection found in hardware system {hardware_system.id} for "
            f"microcontroller_id={microcontroller_id!r}, event_name={event_name!r}"
        )

    def _validate_condition_against_connection(
        self,
        condition,
        connection: "Connection",
    ) -> None:
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
        connection: "Connection",
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
