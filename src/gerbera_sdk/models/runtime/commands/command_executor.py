from dataclasses import dataclass

from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.hardware_plan import HardwarePlan, ResolvedConnection
from gerbera_sdk.models.runtime.boards.board_runtime import BoardRuntime
from gerbera_sdk.models.runtime.commands.command_response import CommandResponseRegistry, CommandRoute
from gerbera_sdk.models.runtime.commands.command_runtime import CommandCompiler
from gerbera_sdk.firmware.configurations import get_device_builder


@dataclass
class CommandExecutor:
    hardware_plan: HardwarePlan
    boards: BoardRuntime
    responses: CommandResponseRegistry
    timeout_seconds: float = 1.0

    def execute_declared(self, connection: Connection, action: str, params: dict[str, object]) -> dict[str, object]:
        key = (connection.microcontroller_id, connection.name)
        return self.execute(self.hardware_plan.connections_by_key[key], action, params)

    def execute(
        self,
        connection: ResolvedConnection,
        action: str,
        params: dict[str, object],
    ) -> dict[str, object]:
        pending = None
        try:
            command = CommandCompiler.build_command(connection, action, params)
            spec = CommandCompiler.command_spec_for_action(connection, action)
            fields = get_device_builder(connection.component_type).config.state.fields
            response_fields = {name: fields[name] for name in spec.response_fields}
            pending = self.responses.register(CommandRoute(connection.microcontroller_id, connection.event_name), response_fields)
            command = CommandCompiler.attach_command_id(command, pending.command_id)
            self.boards.get_transport(connection.microcontroller_id).write(command)
            payload = self.responses.wait(pending, self.timeout_seconds)
        except Exception as exc:
            if pending is not None:
                self.responses.fail(pending.command_id, str(exc))
            return {"success": False, "error": str(exc)}
        return {"success": True, "value": payload}
