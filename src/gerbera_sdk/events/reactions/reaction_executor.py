import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from mcp.types import ToolAnnotations
from pydantic import JsonValue, TypeAdapter, ValidationError

from gerbera_sdk.events.reactions.reaction_schema import ReactionActionSchema

REACTION_MANAGEMENT_TOOLS = frozenset(
    {
        "create_reaction",
        "delete_reaction",
        "list_reactions",
    }
)


@dataclass(frozen=True)
class RegisteredReactionTool:
    function: Callable[..., Any]
    annotations: ToolAnnotations

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
class ReactionToolRegistry:
    tools: dict[str, RegisteredReactionTool] = field(default_factory=dict)

    def register(
        self,
        name: str,
        function: Callable[..., Any],
        annotations: ToolAnnotations,
    ) -> None:
        self.tools[name] = RegisteredReactionTool(function, annotations)

    def validate_action(self, action: ReactionActionSchema) -> None:
        tool = self.require_eligible_tool(action.tool_name)
        tool.validate_arguments(action.arguments)

    async def execute(self, action: ReactionActionSchema) -> JsonValue:
        tool = self.require_eligible_tool(action.tool_name)
        return await tool.invoke(action.arguments)

    def require_eligible_tool(self, name: str) -> RegisteredReactionTool:
        try:
            tool = self.tools[name]
        except KeyError as exc:
            raise ValueError(f"Unknown reaction action tool: {name}") from exc
        if name in REACTION_MANAGEMENT_TOOLS:
            raise ValueError(f"Tool cannot be used by a reaction: {name}")
        if tool.annotations.readOnlyHint is not False:
            raise ValueError(
                "Reaction action tool must explicitly modify state: "
                f"{name}"
            )
        return tool
