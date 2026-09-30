import logging
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import JsonValue

from gerbera_sdk.events.event_bus import EventKey
from gerbera_sdk.events.reactions.reaction_condition import (
    parse_value_like,
    reaction_matches,
)
from gerbera_sdk.events.reactions.reaction_executor import ReactionToolRegistry
from gerbera_sdk.events.reactions.reaction_schema import (
    CreateReactionSchema,
    ReactionDefinitionSchema,
    ReactionRuntimeSchema,
    ReactionSchema,
    ReactionTriggerMode,
    ReactionValue,
)
from gerbera_sdk.events.reactions.reaction_store import ReactionStore


@dataclass
class RegisteredReaction:
    definition: ReactionDefinitionSchema
    latest_value: ReactionValue | None = None
    trigger_count: int = 0
    last_triggered_at: datetime | None = None
    last_completed_at: datetime | None = None
    last_result: JsonValue | None = None
    last_error: str | None = None
    last_triggered_monotonic: float | None = None
    is_executing: bool = False

    def snapshot(self) -> ReactionSchema:
        return ReactionSchema(
            definition=self.definition,
            runtime=ReactionRuntimeSchema(
                latest_value=self.latest_value,
                trigger_count=self.trigger_count,
                last_triggered_at=self.last_triggered_at,
                last_completed_at=self.last_completed_at,
                last_result=self.last_result,
                last_error=self.last_error,
            ),
        )


@dataclass
class ReactionBus:
    action_executor: ReactionToolRegistry | None = None
    store: ReactionStore = field(default_factory=ReactionStore)
    reactions: dict[UUID, RegisteredReaction] = field(default_factory=dict)
    reaction_ids_by_event: dict[EventKey, set[UUID]] = field(
        default_factory=dict
    )
    lock: threading.RLock = field(
        default_factory=threading.RLock,
        init=False,
        repr=False,
    )

    def configure_executor(self, executor: ReactionToolRegistry) -> None:
        self.action_executor = executor

    def create_reaction(
        self,
        request: CreateReactionSchema,
    ) -> ReactionSchema:
        definition = ReactionDefinitionSchema(
            **request.model_dump(),
            reaction_id=uuid4(),
            created_at=datetime.now(timezone.utc),
        )
        self.register_definition(definition)
        return self.get_reaction(definition.reaction_id)

    def register_definition(
        self,
        definition: ReactionDefinitionSchema,
        persist: bool = True,
    ) -> None:
        reaction_id = definition.reaction_id
        with self.lock:
            if reaction_id in self.reactions:
                raise ValueError(f"Duplicate reaction ID: {reaction_id}")
            if persist:
                self.store.save(definition)
            self.reactions[reaction_id] = RegisteredReaction(definition)
            self.reaction_ids_by_event.setdefault(
                definition.event.event_key,
                set(),
            ).add(reaction_id)

    def list_reactions(self) -> list[ReactionSchema]:
        with self.lock:
            registered = sorted(
                self.reactions.values(),
                key=lambda reaction: (
                    reaction.definition.created_at,
                    str(reaction.definition.reaction_id),
                ),
            )
            return [reaction.snapshot() for reaction in registered]

    def get_reaction(self, reaction_id: UUID) -> ReactionSchema:
        with self.lock:
            try:
                return self.reactions[reaction_id].snapshot()
            except KeyError as exc:
                raise ValueError(
                    f"Reaction is not registered: {reaction_id}"
                ) from exc

    def delete_reaction(self, reaction_id: UUID) -> ReactionDefinitionSchema:
        with self.lock:
            if reaction_id not in self.reactions:
                raise ValueError(
                    f"Reaction is not registered: {reaction_id}"
                )
            self.store.delete(reaction_id)
            reaction = self.remove_reaction(reaction_id)
        return reaction.definition

    def remove_reaction(self, reaction_id: UUID) -> RegisteredReaction:
        try:
            reaction = self.reactions.pop(reaction_id)
        except KeyError as exc:
            raise ValueError(
                f"Reaction is not registered: {reaction_id}"
            ) from exc
        event_key = reaction.definition.event.event_key
        reaction_ids = self.reaction_ids_by_event[event_key]
        reaction_ids.remove(reaction_id)
        if not reaction_ids:
            del self.reaction_ids_by_event[event_key]
        return reaction

    async def update_reaction_value(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
        payload: Mapping[str, object],
    ) -> list[JsonValue]:
        event_key = (event_type, microcontroller_id, event_name)
        with self.lock:
            reaction_ids = tuple(
                self.reaction_ids_by_event.get(event_key, ())
            )

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
            payload_field = reaction.definition.event.payload_field
            if payload_field not in payload:
                return None
            try:
                reaction.latest_value = parse_value_like(
                    payload[payload_field],
                    reaction.definition.condition.expected_value,
                )
                matches = reaction_matches(
                    reaction.definition.condition,
                    reaction.latest_value,
                )
            except ValueError as exc:
                reaction.last_error = str(exc)
                return None
            if not matches or not self.claim_execution(reaction):
                return None

            definition = reaction.definition
            is_once = definition.trigger_mode == ReactionTriggerMode.ONCE
            if is_once:
                self.store.delete(reaction_id)
                self.remove_reaction(reaction_id)

        return await self.execute_reaction(reaction)

    def claim_execution(self, reaction: RegisteredReaction) -> bool:
        if reaction.is_executing:
            return False
        now = time.monotonic()
        last_triggered = reaction.last_triggered_monotonic
        if last_triggered is not None:
            elapsed = now - last_triggered
            if elapsed < reaction.definition.cooldown_seconds:
                return False
        reaction.is_executing = True
        reaction.trigger_count += 1
        reaction.last_triggered_at = datetime.now(timezone.utc)
        reaction.last_triggered_monotonic = now
        reaction.last_error = None
        return True

    async def execute_reaction(
        self,
        reaction: RegisteredReaction,
    ) -> JsonValue | None:
        try:
            if self.action_executor is None:
                raise RuntimeError("Reaction action executor is not configured")
            result = await self.action_executor.execute(
                reaction.definition.action
            )
        except Exception as exc:
            with self.lock:
                reaction.last_error = str(exc)
                reaction.last_completed_at = datetime.now(timezone.utc)
                reaction.is_executing = False
            return None

        with self.lock:
            reaction.last_result = result
            reaction.last_completed_at = datetime.now(timezone.utc)
            reaction.is_executing = False
        return result
