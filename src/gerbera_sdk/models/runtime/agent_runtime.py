from collections.abc import Awaitable, Callable, Container
from dataclasses import dataclass, field
import inspect
from pathlib import Path
import sys
from types import ModuleType
from typing import cast
import uuid

from gerbera_sdk.events.rules import (
    OperatorEnum,
    Rule,
    RuleBuffer,
    RuleBus,
    RuleCallback,
    RuleCondition,
    build_rule_callback_script,
    parse_rule_value,
)
from gerbera_sdk.paths import RULES_PATH
from gerbera_sdk.utils import (
    EventKey,
    build_event_key,
    hash_event_key,
    require_configured_mcp_url,
)


RuleScriptCallback = Callable[[str, float], Awaitable[object]]


@dataclass
class AgentRuntime:
    mcp_url: str
    rule_bus: RuleBus
    rule_buffer: RuleBuffer
    rules_path: Path = field(default_factory=lambda: RULES_PATH)
    valid_event_keys: Container[EventKey] | None = None

    def insert_rule(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
        expected_value: float,
        operator: OperatorEnum,
        callback_body: str,
    ) -> dict[str, str]:
        configured_mcp_url = require_configured_mcp_url(self.mcp_url)
        normalized_expected = parse_rule_value(expected_value)
        event_key = build_event_key(
            event_type,
            microcontroller_id,
            event_name,
        )
        if (
            self.valid_event_keys is not None
            and event_key not in self.valid_event_keys
        ):
            raise ValueError(f"Event key is not registered: {event_key}")
        if self.rule_bus.get_rule(event_key) is not None:
            raise ValueError(f"Rule already registered for event: {event_key}")

        rule_id = str(uuid.uuid4())
        script_path = self._rule_script_path(event_key)
        callback = self._write_and_load_callback(
            script_path=script_path,
            module_name=f"_gerbera_rule_{rule_id.replace('-', '_')}",
            callback_script=build_rule_callback_script(callback_body),
        )
        rule = Rule(
            condition=RuleCondition(
                expected=normalized_expected,
                operator=operator,
            ),
            callback=RuleCallback(
                callback=callback,
                mcp_url=configured_mcp_url,
            ),
            id=rule_id,
        )

        self.rule_bus.register_rule(
            event_type=event_type,
            microcontroller_id=microcontroller_id,
            event_name=event_name,
            rule=rule,
        )
        self.rule_buffer.register_event_in_buffer(
            event_type=event_type,
            microcontroller_id=microcontroller_id,
            event_name=event_name,
        )

        return {
            "rule_id": rule.id,
            "script_path": str(script_path),
        }

    def delete_rule(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
    ) -> dict[str, str]:
        event_key = build_event_key(
            event_type,
            microcontroller_id,
            event_name,
        )
        rule = self.rule_bus.get_rule(event_key)
        if rule is None:
            raise ValueError(f"Rule is not registered for event: {event_key}")

        script_path = self._rule_script_path(event_key)
        self.rule_bus.unregister_rule(
            event_type=event_type,
            microcontroller_id=microcontroller_id,
            event_name=event_name,
        )
        self.rule_buffer.unregister_event_from_buffer(
            event_type=event_type,
            microcontroller_id=microcontroller_id,
            event_name=event_name,
        )
        sys.modules.pop(f"_gerbera_rule_{rule.id.replace('-', '_')}", None)
        script_path.unlink(missing_ok=True)

        return {
            "rule_id": rule.id,
            "script_path": str(script_path),
        }

    def _rule_script_path(
        self,
        event_key: EventKey,
    ) -> Path:
        return self.rules_path / f"{hash_event_key(event_key)}.py"

    def _write_and_load_callback(
        self,
        script_path: Path,
        module_name: str,
        callback_script: str,
    ) -> RuleScriptCallback:
        self.rules_path.mkdir(parents=True, exist_ok=True)
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
                    "Rule script must define async callback(mcp_url, value)"
                )

            return cast(RuleScriptCallback, callback)
        except Exception:
            sys.modules.pop(module_name, None)
            script_path.unlink(missing_ok=True)
            raise
