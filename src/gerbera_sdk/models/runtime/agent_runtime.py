from collections.abc import Awaitable, Callable, Container
from dataclasses import dataclass, field
import inspect
from pathlib import Path
import sys
from types import ModuleType
from typing import cast
import uuid

from gerbera_sdk.events.reactions import (
    OperatorEnum,
    Reaction,
    ReactionBus,
    ReactionCallback,
    ReactionCondition,
    ReactionTriggerModeEnum,
    build_reaction_callback_script,
    parse_reaction_value,
)
from gerbera_sdk.paths import REACTIONS_PATH
from gerbera_sdk.utils import hash_event_key


ReactionScriptCallback = Callable[[str, float], Awaitable[object]]


@dataclass
class AgentRuntime:
    mcp_url: str
    reaction_bus: ReactionBus
    reactions_path: Path = field(default_factory=lambda: REACTIONS_PATH)
    valid_event_keys: Container[tuple[str, str, str]] | None = None

    def insert_reaction(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
        expected_value: float,
        operator: OperatorEnum,
        callback_body: str,
        trigger_mode: ReactionTriggerModeEnum = ReactionTriggerModeEnum.REPEAT,
    ) -> dict[str, str]:
        normalized_expected = parse_reaction_value(expected_value)
        event_key = (
            event_type,
            microcontroller_id,
            event_name,
        )
        if (
            self.valid_event_keys is not None
            and event_key not in self.valid_event_keys
        ):
            raise ValueError(f"Event key is not registered: {event_key}")
        if self.reaction_bus.get_reaction(event_key) is not None:
            raise ValueError(f"Reaction already registered for event: {event_key}")

        reaction_id = str(uuid.uuid4())
        script_path = self._reaction_script_path(event_key)
        callback = self._write_and_load_callback(
            script_path=script_path,
            module_name=f"_gerbera_reaction_{reaction_id.replace('-', '_')}",
            callback_script=build_reaction_callback_script(callback_body),
        )
        reaction = Reaction(
            condition=ReactionCondition(
                expected=normalized_expected,
                operator=operator,
            ),
            callback=ReactionCallback(
                callback=callback,
                mcp_url=self.mcp_url,
            ),
            trigger_mode=trigger_mode,
            id=reaction_id,
        )

        self.reaction_bus.register_reaction(
            event_type=event_type,
            microcontroller_id=microcontroller_id,
            event_name=event_name,
            reaction=reaction,
        )
        return {
            "reaction_id": reaction.id,
            "script_path": str(script_path),
        }

    def delete_reaction(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
    ) -> dict[str, str]:
        event_key = (
            event_type,
            microcontroller_id,
            event_name,
        )
        reaction = self.reaction_bus.get_reaction(event_key)
        if reaction is None:
            raise ValueError(f"Reaction is not registered for event: {event_key}")

        script_path = self._reaction_script_path(event_key)
        self.reaction_bus.unregister_reaction(
            event_type=event_type,
            microcontroller_id=microcontroller_id,
            event_name=event_name,
        )
        sys.modules.pop(f"_gerbera_reaction_{reaction.id.replace('-', '_')}", None)
        script_path.unlink(missing_ok=True)

        return {
            "reaction_id": reaction.id,
            "script_path": str(script_path),
        }

    def _reaction_script_path(
        self,
        event_key: tuple[str, str, str],
    ) -> Path:
        return self.reactions_path / f"{hash_event_key(event_key)}.py"

    def _write_and_load_callback(
        self,
        script_path: Path,
        module_name: str,
        callback_script: str,
    ) -> ReactionScriptCallback:
        self.reactions_path.mkdir(parents=True, exist_ok=True)
        script_path.write_text(callback_script)

        try:
            module = ModuleType(module_name)
            module.__file__ = str(script_path)
            sys.modules[module_name] = module
            code = compile(
                callback_script,
                str(script_path),
                "exec",
            )
            exec(code, module.__dict__)

            callback = getattr(module, "callback", None)
            if not inspect.iscoroutinefunction(callback):
                raise TypeError(
                    "Reaction script must define async callback(mcp_url, value)"
                )

            return cast(ReactionScriptCallback, callback)
        except Exception:
            sys.modules.pop(module_name, None)
            script_path.unlink(missing_ok=True)
            raise
