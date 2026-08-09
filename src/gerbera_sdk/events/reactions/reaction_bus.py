from dataclasses import dataclass, field
import uuid

from gerbera_sdk.events.reactions.reaction import Reaction


@dataclass
class ReactionBus:
    reaction_bus: dict[tuple[str, str, str], Reaction] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def register_reaction(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
        reaction: Reaction,
    ) -> None:
        event_key = (
            event_type,
            microcontroller_id,
            event_name,
        )

        if event_key in self.reaction_bus:
            raise ValueError(f"Reaction already registered for event: {event_key}")

        self.reaction_bus[event_key] = reaction

    def unregister_reaction(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
    ) -> Reaction:
        event_key = (
            event_type,
            microcontroller_id,
            event_name,
        )
        try:
            return self.reaction_bus.pop(event_key)
        except KeyError as exc:
            raise ValueError(f"Reaction is not registered for event: {event_key}") from exc

    def get_reaction(self, event_key: tuple[str, str, str]) -> Reaction | None:
        return self.reaction_bus.get(event_key)

    async def emit_evaluation_event(
        self,
        event_key: tuple[str, str, str],
        actual: float,
    ) -> object | None:
        reaction = self.get_reaction(event_key)
        if reaction is None:
            return

        if not reaction.condition.evaluate_condition(actual):
            return

        if not reaction.claim_trigger():
            return

        return await reaction.callback(val=actual)
