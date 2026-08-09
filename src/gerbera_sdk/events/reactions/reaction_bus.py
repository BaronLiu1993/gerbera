from dataclasses import dataclass, field
from collections.abc import Mapping

from gerbera_sdk.events.reactions.reaction import Reaction
from gerbera_sdk.events.reactions.reaction_condition import parse_reaction_value


@dataclass
class ReactionBus:
    reaction_bus: dict[tuple[str, str, str], Reaction] = field(default_factory=dict)
    latest_values: dict[tuple[str, str, str], float | None] = field(
        default_factory=dict
    )

    def register_reaction(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
        reaction: Reaction,
    ) -> None:
        reaction_key = (
            event_type,
            microcontroller_id,
            event_name,
        )

        if reaction_key in self.reaction_bus:
            raise ValueError(f"Reaction already registered for event: {reaction_key}")

        self.reaction_bus[reaction_key] = reaction
        self.latest_values[reaction_key] = reaction.latest_value

    def unregister_reaction(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
    ) -> Reaction:
        reaction_key = (
            event_type,
            microcontroller_id,
            event_name,
        )
        try:
            reaction = self.reaction_bus.pop(reaction_key)
        except KeyError as exc:
            raise ValueError(
                f"Reaction is not registered for event: {reaction_key}"
            ) from exc

        self.latest_values.pop(reaction_key, None)
        return reaction

    def get_reaction(self, reaction_key: tuple[str, str, str]) -> Reaction | None:
        return self.reaction_bus.get(reaction_key)

    async def emit_evaluation_event(
        self,
        reaction_key: tuple[str, str, str],
        latest_value: float,
    ) -> object | None:
        reaction = self.reaction_bus.get(reaction_key)
        if reaction is None:
            return

        reaction.latest_value = latest_value
        self.latest_values[reaction_key] = latest_value
        return await reaction.perform_work()

    async def update_reaction_value(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
        payload: Mapping[str, object],
    ) -> object | None:
        reaction_key = (
            event_type,
            microcontroller_id,
            event_name,
        )

        reaction = self.reaction_bus.get(reaction_key)
        if reaction is None or len(payload) != 1:
            return

        latest_value = parse_reaction_value(next(iter(payload.values())))
        return await self.emit_evaluation_event(reaction_key, latest_value)
