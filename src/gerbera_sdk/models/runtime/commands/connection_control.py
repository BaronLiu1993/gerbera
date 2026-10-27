from dataclasses import dataclass

from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event_worker import EventWorker
from gerbera_sdk.models.hardware.hardware_plan import ResolvedConnection, StateKey
from gerbera_sdk.models.runtime.commands.command_runtime import CommandCompiler
from gerbera_sdk.models.runtime.state.hardware_runtime import ConnectionState, HardwareRuntime


@dataclass
class ConnectionControl:
    events: EventBus
    worker: EventWorker
    state: HardwareRuntime

    def set_state(self, connection: ResolvedConnection, value: int) -> dict[str, object]:
        response = connection.perform_action("WRITE", {"state": value})
        if response["success"]:
            key = CommandCompiler.state_keys(connection)[0]
            self.record_state(key, value)
        return response

    def set_stream_state(self, connection: ResolvedConnection, value: int) -> dict[str, object]:
        response = connection.perform_action("WRITE", {"state": value})
        if value == 0:
            event = self.events.get_event("STREAM", connection.microcontroller_id, connection.event_name)
            event.flush()
            self.worker.wait_until_idle()
        if response["success"]:
            self.record_state(CommandCompiler.state_key(connection, "stream_enabled"), value)
        return response

    def record_state(self, key: StateKey, value: int) -> None:
        self.state.update_state(key, ConnectionState(value=str(value), unit=None))
