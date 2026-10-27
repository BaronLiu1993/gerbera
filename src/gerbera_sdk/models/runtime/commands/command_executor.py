from dataclasses import dataclass
from functools import partial

from gerbera_sdk.firmware.command_definitions import command_specs
from gerbera_sdk.models.hardware.hardware_plan import HardwarePlan, ResolvedConnection
from gerbera_sdk.models.runtime.boards.board_runtime import BoardRuntime
from gerbera_sdk.models.runtime.commands.command_response import CommandResponseRegistry
from gerbera_sdk.models.runtime.commands.command_runtime import CommandCompiler


@dataclass
class CommandExecutor:
    hardware_plan: HardwarePlan
    boards: BoardRuntime
    responses: CommandResponseRegistry
    timeout_seconds: float = 1.0

    def bind_actions(self) -> None:
        for board in self.hardware_plan.boards:
            for connection in board.connections:
                for command in command_specs(connection):
                    connection.register_action(
                        command.method,
                        partial(self.execute, connection, command.method),
                    )

    def execute(
        self,
        connection: ResolvedConnection,
        action: str,
        params: dict[str, object],
    ) -> dict[str, object]:
        pending = self.responses.register(connection.microcontroller_id)
        try:
            command = CommandCompiler.build_command(connection, action, params)
            command = CommandCompiler.attach_command_id(command, pending.command_id)
            self.boards.get_transport(connection.microcontroller_id).write(command)
            payload = self.responses.wait(pending, self.timeout_seconds)
        except Exception as exc:
            self.responses.fail(pending.command_id, str(exc))
            return {"success": False, "error": str(exc)}
        return {"success": True, "value": payload}
