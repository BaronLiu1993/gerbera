from dataclasses import dataclass
from typing import Annotated, Any, Callable

from mcp.types import ToolAnnotations
from pydantic import AfterValidator, Field
from gerbera_sdk.firmware.parameter_schema import NumericChoice

from gerbera_sdk.models.runtime.server.tool_registry import McpToolRegistry, ToolDefinition
from inspect import Parameter, Signature
from gerbera_sdk.models.runtime.commands.command_executor import CommandExecutor
from gerbera_sdk.models.runtime.commands.connection_control import ConnectionControl

from gerbera_sdk.firmware.firmware_schema import CommandSpec, ParameterSpec
from gerbera_sdk.models.hardware.hardware_plan import (
    HardwarePlan,
    ResolvedConnection,
)
from gerbera_sdk.models.runtime.commands.command_runtime import CommandCompiler
from gerbera_sdk.models.runtime.server.command_annotations import command_annotations
from gerbera_sdk.models.runtime.state.hardware_runtime import HardwareRuntime


@dataclass
class HardwareTools:
    tools: McpToolRegistry
    hardware_plan: HardwarePlan
    hardware_runtime: HardwareRuntime
    controls: ConnectionControl
    commands: CommandExecutor

    def build_tool_function(
        self,
        connection: ResolvedConnection,
        command: CommandSpec,
    ) -> Callable[..., dict[str, object]]:
        action = command.method.strip().upper()
        if not command.params:

            def tool_function() -> dict[str, object]:
                return self.commands.execute(connection, action, {})

            return tool_function

        def tool_function(**values: Any) -> dict[str, object]:
            params = {
                name: value for name, value in values.items() if value is not None
            }
            return self.commands.execute(connection, action, params)

        parameters: list[Parameter] = []
        annotations: dict[str, Any] = {"return": dict[str, object]}
        for name, parameter in command.params.items():
            annotation = self.build_parameter_annotation(parameter)
            default = Parameter.empty if parameter.required else None
            if not parameter.required:
                annotation |= None
            annotations[name] = annotation
            parameters.append(
                Parameter(
                    name=name,
                    kind=Parameter.KEYWORD_ONLY,
                    default=default,
                    annotation=annotation,
                )
            )

        tool_function.__annotations__ = annotations
        tool_function.__signature__ = Signature(
            parameters=parameters,
            return_annotation=dict[str, object],
        )
        return tool_function

    def build_parameter_annotation(
        self,
        parameter: ParameterSpec,
    ) -> Any:
        return Annotated[
            float,
            Field(
                description=parameter.description or None,
                strict=True,
                allow_inf_nan=False,
                json_schema_extra=parameter.domain.json_constraints(),
            ),
            AfterValidator(parameter.domain.validate_value),
        ]

    def register_connection_tool(
        self,
        connection: ResolvedConnection,
        command: CommandSpec,
        annotations: ToolAnnotations,
    ) -> None:
        description = command.description.strip()
        if not description:
            raise ValueError(
                f"Command description is required: "
                f"{command.method},{connection.name}"
            )
        if connection.stream_enabled:
            description += (
                f" Collected data is stored in table " f"`{connection.event_name}`."
            )

        action = command.method.strip().lower()
        tool_name = f"{action}_{connection.name}"
        state_key = CommandCompiler.state_keys(connection)[0]
        tool_function = self.build_tool_function(
            connection,
            command,
        )
        self.tools.register(ToolDefinition(
            name=tool_name,
            description=description,
            tool_function=tool_function,
            annotations=annotations,
            meta={
                "key": self.hardware_runtime.state_key_label(state_key),
            },
        ))

    def state_toggle(self, connection: ResolvedConnection, state: int) -> Callable[[], dict[str, object]]:
        def tool_function() -> dict[str, object]:
            return self.controls.set_state(connection, state)
        return tool_function

    def stream_toggle(self, connection: ResolvedConnection, state: int) -> Callable[[], dict[str, object]]:
        def tool_function() -> dict[str, object]:
            return self.controls.set_stream_state(connection, state)
        return tool_function

    def register_state_toggle_tools(
        self, connection: ResolvedConnection, annotations: ToolAnnotations,
    ) -> None:
        state_key = CommandCompiler.state_keys(connection)[0]
        for state, verb in ((1, "on"), (0, "off")):
            description = f"Turn {verb} {connection.name}."
            self.tools.register(ToolDefinition(
                name=f"turn_{verb}_{connection.name}",
                description=description,
                tool_function=self.state_toggle(connection, state),
                annotations=annotations.model_copy(update={"title": description.rstrip(".")}),
                meta={"key": self.hardware_runtime.state_key_label(state_key)},
            ))

    def register_stream_toggle_tools(
        self, connection: ResolvedConnection, annotations: ToolAnnotations,
    ) -> None:
        state_key = CommandCompiler.state_key(connection, "stream_enabled")
        for state, verb in ((1, "on"), (0, "off")):
            description = f"Turn {verb} continuous streaming for {connection.name}."
            self.tools.register(ToolDefinition(
                name=f"turn_{verb}_{connection.name}_stream",
                description=description,
                tool_function=self.stream_toggle(connection, state),
                annotations=annotations.model_copy(update={"title": description.rstrip(".")}),
                meta={"key": self.hardware_runtime.state_key_label(state_key)},
            ))

    def register_hardware_tools(self) -> None:
        for board in self.hardware_plan.boards:
            for connection in board.connections:
                self.register_connection_tools(connection)


    @staticmethod
    def command_is_state_toggle(command: CommandSpec) -> bool:
        if command.method.strip().upper() != "WRITE":
            return False

        state = command.params.get("state")
        return (
            state is not None and isinstance(state.domain, NumericChoice)
            and set(state.domain.values) == {0.0, 1.0}
        )

    @classmethod
    def connection_supports_state_toggle(
        cls,
        connection: ResolvedConnection,
    ) -> bool:
        for command in CommandCompiler.command_specs(connection):
            if cls.command_is_state_toggle(command):
                return True
        return False

    @classmethod
    def connection_supports_stream_toggle(
        cls,
        connection: ResolvedConnection,
    ) -> bool:
        return connection.stream_enabled and cls.connection_supports_state_toggle(
            connection
        )

    def register_connection_tools(
        self,
        connection: ResolvedConnection,
    ) -> None:
        commands = CommandCompiler.command_specs(connection)
        supports_stream = self.connection_supports_stream_toggle(connection)
        for command in commands:
            annotations = command_annotations(connection, command)
            if not (supports_stream and self.command_is_state_toggle(command)):
                self.register_connection_tool(connection, command, annotations)

        if not self.connection_supports_state_toggle(connection):
            return

        for command in commands:
            if self.command_is_state_toggle(command):
                toggle_command = command
                break
        else:
            raise RuntimeError("State toggle command is not registered")
        toggle_annotations = command_annotations(
            connection,
            toggle_command,
        )
        if supports_stream:
            self.register_stream_toggle_tools(connection, toggle_annotations)
        else:
            self.register_state_toggle_tools(connection, toggle_annotations)
