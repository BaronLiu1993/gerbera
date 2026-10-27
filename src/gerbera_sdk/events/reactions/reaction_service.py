from dataclasses import dataclass
import logging
from uuid import UUID

from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.reactions.reaction_bus import ReactionBus
from gerbera_sdk.events.reactions.reaction_executor import ReactionToolRegistry
from gerbera_sdk.events.reactions.reaction_schema import CreateReactionSchema, ReactionEventSchema, ReactionSchema
from gerbera_sdk.models.hardware.hardware_plan import HardwarePlan
from gerbera_sdk.models.runtime.commands.command_runtime import CommandCompiler

LOGGER = logging.getLogger(__name__)


@dataclass
class ReactionService:
    hardware_plan: HardwarePlan
    event_bus: EventBus
    reaction_bus: ReactionBus
    reaction_tool_registry: ReactionToolRegistry

    def validate_reaction_event(self, event: ReactionEventSchema) -> None:
        try:
            self.event_bus.get_event(*event.event_key)
        except RuntimeError as exc:
            raise ValueError(
                f"Unknown reaction event: {event.event_key}"
            ) from exc

        route = (event.microcontroller_id, event.event_name)
        connection = self.hardware_plan.connections_by_event_route[route]
        payload_fields = {
            state_key[2]
            for state_key in CommandCompiler.state_keys(connection)
        }
        if event.payload_field not in payload_fields:
            raise ValueError(
                "Unknown reaction payload field: "
                f"{event.payload_field} for {event.event_name}"
            )


    def validate_reaction_definition(
        self,
        definition: CreateReactionSchema,
    ) -> None:
        self.validate_reaction_event(definition.event)
        self.reaction_tool_registry.validate_action(definition.action)


    def restore_reactions(self) -> None:
        for definition in self.reaction_bus.store.load():
            try:
                self.validate_reaction_definition(definition)
                self.reaction_bus.register_definition(
                    definition,
                    persist=False,
                )
            except ValueError as exc:
                LOGGER.warning(
                    "Ignoring unusable stored reaction %s: %s",
                    definition.reaction_id,
                    exc,
                )


    def event_catalog(
        self,
    ) -> dict[str, dict[str, dict[str, dict[str, object]]]]:
        catalog: dict[str, dict[str, dict[str, dict[str, object]]]] = {}

        for event_key, event in self.event_bus.events.items():
            event_type, microcontroller_id, event_name = event_key
            connection = self.hardware_plan.connections_by_event_route[
                (microcontroller_id, event_name)
            ]
            metadata: dict[str, object] = {
                "event_type": event_type,
                "microcontroller_id": microcontroller_id,
                "event_name": event_name,
                "connection_name": connection.name,
                "component_type": connection.component_type,
                "description": connection.description,
                "streamable": event.streamable,
            }
            catalog.setdefault(event_type, {}).setdefault(
                microcontroller_id,
                {},
            )[event_name] = metadata

        return catalog


    def create_reaction(self, request: CreateReactionSchema) -> ReactionSchema:
        self.validate_reaction_definition(request)
        return self.reaction_bus.create_reaction(request)

    def list_reactions(self) -> list[ReactionSchema]:
        return self.reaction_bus.list_reactions()

    def delete_reaction(self, reaction_id: UUID) -> bool:
        return self.reaction_bus.delete_reaction(reaction_id)
