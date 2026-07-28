from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
import inspect
from pathlib import Path
import sys
from types import ModuleType
from typing import Any, cast
import uuid

from gerbera_sdk.events.rules import (
    OperatorEnum,
    Rule,
    RuleBuffer,
    RuleBus,
    RuleCallback,
    RuleCondition,
    RuleValue,
)
from gerbera_sdk.paths import RULES_PATH
from gerbera_sdk.utils import build_event_key


RuleScriptCallback = Callable[[str, RuleValue], Awaitable[Any]]


@dataclass
class AgentRuntime:
    mcp_url: str
    rule_bus: RuleBus
    rule_buffer: RuleBuffer
    rules_path: Path = field(default_factory=lambda: RULES_PATH)

    def insert_rule(
        self,
        event_type: str,
        microcontroller_id: str,
        event_name: str,
        expected_value: RuleValue,
        operator: OperatorEnum,
        callback_script: str,
    ) -> dict[str, str]:
        event_key = build_event_key(
            event_type,
            microcontroller_id,
            event_name,
        )
        if self.rule_bus.get_rule(event_key) is not None:
            raise ValueError(f"Rule already registered for event: {event_key}")

        rule_id = str(uuid.uuid4())
        script_path = self.rules_path / f"{rule_id}.py"
        callback = self._write_and_load_callback(
            script_path=script_path,
            module_name=f"_gerbera_rule_{rule_id.replace('-', '_')}",
            callback_script=callback_script,
        )
        rule = Rule(
            condition=RuleCondition(
                expected=expected_value,
                operator=operator,
            ),
            callback=RuleCallback(
                callback=callback,
                mcp_url=self.mcp_url,
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
