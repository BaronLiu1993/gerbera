import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import JsonValue, TypeAdapter, ValidationError

from gerbera_sdk.events.reactions.reaction_schema import ReactionActionSchema


@dataclass(frozen=True)
class RegisteredAction:
    function: Callable[..., Any]

    def validate_arguments(self, arguments: dict[str, JsonValue]) -> None:
        signature = inspect.signature(self.function)
        try:
            bound_arguments = signature.bind(**arguments)
        except TypeError as exc:
            raise ValueError(f"Invalid reaction action arguments: {exc}") from exc

        for name, value in bound_arguments.arguments.items():
            annotation = signature.parameters[name].annotation
            if annotation is inspect.Parameter.empty:
                continue
            try:
                TypeAdapter(annotation).validate_python(value)
            except ValidationError as exc:
                raise ValueError(
                    f"Invalid reaction action argument: {name}"
                ) from exc

    async def invoke(self, arguments: dict[str, JsonValue]) -> JsonValue:
        result = self.function(**arguments)
        if inspect.isawaitable(result):
            result = await result
        try:
            return TypeAdapter(JsonValue).validate_python(result)
        except ValidationError:
            return str(result)


@dataclass
class ReactionActionRegistry:
    actions: dict[str, RegisteredAction] = field(default_factory=dict)

    def register(
        self,
        name: str,
        function: Callable[..., Any],
    ) -> None:
        self.actions[name] = RegisteredAction(function)

    def validate_action(self, action: ReactionActionSchema) -> None:
        registered = self.require_action(action.tool_name)
        registered.validate_arguments(action.arguments)

    async def execute(self, action: ReactionActionSchema) -> JsonValue:
        registered = self.require_action(action.tool_name)
        return await registered.invoke(action.arguments)

    def require_action(self, name: str) -> RegisteredAction:
        try:
            registered = self.actions[name]
        except KeyError as exc:
            raise ValueError(f"Unknown reaction action: {name}") from exc
        return registered
