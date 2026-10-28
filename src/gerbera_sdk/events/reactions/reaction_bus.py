import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import JsonValue

from gerbera_sdk.events.reactions.reaction_condition import (
    parse_value_like,
    reaction_matches,
)
from gerbera_sdk.events.reactions.reaction_executor import ReactionActionRegistry
from gerbera_sdk.events.reactions.reaction_schema import (
    CreateReactionSchema,
    ReactionSchema,
    ReactionTriggerMode,
)
from gerbera_sdk.events.reactions.reaction_store import ReactionStore


@dataclass
class ReactionBus:
    action_executor: ReactionActionRegistry | None = None
    store: ReactionStore = field(default_factory=ReactionStore)
    reactions: dict[UUID, ReactionSchema] = field(default_factory=dict)
    lock: threading.RLock = field(
        default_factory=threading.RLock,
        init=False,
        repr=False,
    )

    def configure_executor(self, executor: ReactionActionRegistry) -> None:
        self.action_executor = executor

    def create_reaction(
        self,
        request: CreateReactionSchema,
    ) -> ReactionSchema:
        definition = ReactionSchema(
            **request.model_dump(),
            reaction_id=uuid4(),
            created_at=datetime.now(timezone.utc),
        )
        self.register_definition(definition)
        return self.get_reaction(definition.reaction_id)

    def register_definition(
        self,
        definition: ReactionSchema,
        persist: bool = True,
    ) -> None:
        reaction_id = definition.reaction_id
        with self.lock:
            if reaction_id in self.reactions:
                raise ValueError(f"Duplicate reaction ID: {reaction_id}")
            if persist:
                self.store.save(definition)
            self.reactions[reaction_id] = definition

    def list_reactions(self) -> list[ReactionSchema]:
        with self.lock:
            registered = sorted(
                self.reactions.values(),
                key=lambda reaction: (
                    reaction.created_at,
                    str(reaction.reaction_id),
                ),
            )
            return [reaction.model_copy(deep=True) for reaction in registered]

    def get_reaction(self, reaction_id: UUID) -> ReactionSchema:
        with self.lock:
            try:
                return self.reactions[reaction_id].model_copy(deep=True)
            except KeyError as exc:
                raise ValueError(
                    f"Reaction is not registered: {reaction_id}"
                ) from exc

    def delete_reaction(self, reaction_id: UUID) -> ReactionSchema:
        with self.lock:
            if reaction_id not in self.reactions:
                raise ValueError(
                    f"Reaction is not registered: {reaction_id}"
                )
            self.store.delete(reaction_id)
            reaction = self.remove_reaction(reaction_id)
        return reaction

    def remove_reaction(self, reaction_id: UUID) -> ReactionSchema:
        try:
            return self.reactions.pop(reaction_id)
        except KeyError as exc:
            raise ValueError(
                f"Reaction is not registered: {reaction_id}"
            ) from exc

    async def update_reaction_value(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
        payload: Mapping[str, object],
    ) -> list[JsonValue]:
        event_key = (event_type, microcontroller_id, event_name)
        with self.lock:
            reaction_ids = [
                reaction_id
                for reaction_id, reaction in self.reactions.items()
                if reaction.event.event_key == event_key
            ]

        results: list[JsonValue] = []
        for reaction_id in reaction_ids:
            result = await self.evaluate_reaction(reaction_id, payload)
            if result is not None:
                results.append(result)
        return results

    async def evaluate_reaction(
        self,
        reaction_id: UUID,
        payload: Mapping[str, object],
    ) -> JsonValue | None:
        with self.lock:
            reaction = self.reactions.get(reaction_id)
            if reaction is None:
                return None
            payload_field = reaction.event.payload_field
            if payload_field not in payload:
                return None
            try:
                reaction.latest_value = parse_value_like(
                    payload[payload_field],
                    reaction.condition.expected_value,
                )
                matches = reaction_matches(
                    reaction.condition,
                    reaction.latest_value,
                )
            except ValueError as exc:
                reaction.last_error = str(exc)
                return None
            if not matches or not self.claim_execution(reaction):
                return None

            if reaction.trigger_mode == ReactionTriggerMode.ONCE:
                self.store.delete(reaction_id)
                self.remove_reaction(reaction_id)

        return await self.execute_reaction(reaction)

    def claim_execution(self, reaction: ReactionSchema) -> bool:
        if reaction.is_executing:
            return False
        now = time.monotonic()
        last_triggered = reaction.last_triggered_monotonic
        if last_triggered is not None:
            elapsed = now - last_triggered
            if elapsed < reaction.cooldown_seconds:
                return False
        reaction.is_executing = True
        reaction.trigger_count += 1
        reaction.last_triggered_at = datetime.now(timezone.utc)
        reaction.last_triggered_monotonic = now
        reaction.last_error = None
        return True

    async def execute_reaction(
        self,
        reaction: ReactionSchema,
    ) -> JsonValue | None:
        try:
            if self.action_executor is None:
                raise RuntimeError("Reaction action executor is not configured")
            result = await self.action_executor.execute(
                reaction.action
            )
            with self.lock:
                reaction.last_result = result
            return result
        except Exception as exc:
            with self.lock:
                reaction.last_error = str(exc)
            return None
        finally:
            with self.lock:
                reaction.last_completed_at = datetime.now(timezone.utc)
                reaction.is_executing = False
