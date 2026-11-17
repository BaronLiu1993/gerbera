from collections.abc import AsyncIterator
from contextlib import ExitStack, asynccontextmanager
from pathlib import Path

from fastmcp import FastMCP

from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event_listener import EventListener
from gerbera_sdk.events.event_worker import EventWorker
from gerbera_sdk.events.reactions.reaction_bus import ReactionBus
from gerbera_sdk.events.reactions.reaction_executor import ReactionActionRegistry
from gerbera_sdk.firmware.firmware_generator import FirmwareGenerator
from gerbera_sdk.firmware.firmware_uploader import FirmwareUploader
from gerbera_sdk.models.hardware.hardware_plan import HardwarePlan
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.validation import HardwareContractCompiler
from gerbera_sdk.models.runtime.boards.board_runtime import BoardRuntime
from gerbera_sdk.models.runtime.commands.command_executor import CommandExecutor
from gerbera_sdk.models.runtime.commands.command_response import CommandResponseRegistry
from gerbera_sdk.models.runtime.commands.command_runtime import CommandCompiler
from gerbera_sdk.models.runtime.commands.connection_control import ConnectionControl
from gerbera_sdk.models.runtime.perception.camera_runtime import CameraRuntime
from gerbera_sdk.models.runtime.perception.model_runtime import ModelRuntime
from gerbera_sdk.gerbera_server import GerberaServer
from gerbera_sdk.models.runtime.state.hardware_runtime import HardwareRuntime
from gerbera_sdk.database_runtime import DatabaseRuntime, DatabaseSettings


class GerberaRuntime:
    @staticmethod
    def build_application(hardware: HardwareSystem, database: DatabaseSettings) -> FastMCP:
        plan = GerberaRuntime.validate_hardware(hardware)
        boards = BoardRuntime(hardware)
        cameras = CameraRuntime(hardware)
        models = ModelRuntime(hardware, cameras)
        storage = DatabaseRuntime(hardware, database)
        worker = EventWorker(database=storage)
        state = GerberaRuntime.build_state(plan)
        events = EventBus()
        events.register(plan, worker)
        responses = CommandResponseRegistry()
        commands = CommandExecutor(plan, boards, responses)
        actions = ReactionActionRegistry()
        reactions = ReactionBus(plan, events, actions)
        listener = EventListener(
            hardware_plan=plan, transport_pool=boards.transport_pool,
            event_bus=events, reaction_bus=reactions, hardware_runtime=state,
            command_responses=responses,
        )

        @asynccontextmanager
        async def lifespan(server: FastMCP) -> AsyncIterator[dict[str, object]]:
            storage.prepare()
            models.register_models()
            reactions.restore_reactions()
            with ExitStack() as cleanup:
                cleanup.callback(boards.close)
                boards.start()
                cleanup.callback(cameras.close)
                cameras.start()
                cleanup.callback(models.turn_off_all_model_streams)
                models.turn_on_all_model_streams()
                cleanup.callback(worker.stop)
                worker.start()
                cleanup.callback(worker.queue.join)
                cleanup.callback(events.flush_event_buffers)
                cleanup.callback(listener.stop_listeners)
                listener.create_listeners()
                listener.start_listeners()
                yield {
                    "board_runtime": boards,
                    "camera_runtime": cameras,
                    "event_worker": worker,
                    "model_runtime": models,
                    "hardware_runtime": state,
                }

        app = FastMCP(hardware.name, lifespan=lifespan)
        server = GerberaServer(
            app=app,
            actions=actions,
            hardware_system=hardware,
            hardware_plan=plan,
            hardware_runtime=state,
            controls=ConnectionControl(events, worker, state, commands),
            commands=commands,
            camera_runtime=cameras,
            model_runtime=models,
            reactions=reactions,
            event_bus=events,
        )
        server.register()
        return app

    @staticmethod
    def run(hardware: HardwareSystem, database: DatabaseSettings, **transport_options) -> None:
        GerberaRuntime.build_application(hardware, database).run(**transport_options)

    @staticmethod
    def validate_hardware(hardware: HardwareSystem) -> HardwarePlan:
        GerberaRuntime.bind_connection_microcontroller_ids(hardware)
        return HardwareContractCompiler.compile(hardware)

    @staticmethod
    def bind_connection_microcontroller_ids(hardware: HardwareSystem) -> None:
        GerberaRuntime.validate_declared_ownership(hardware)
        for controller in hardware.microcontrollers:
            controller.hardware_system_id = hardware.id
            controller_id = controller.id
            for connection in controller.connections:
                connection.microcontroller_id = controller_id

    @staticmethod
    def validate_declared_ownership(hardware: HardwareSystem) -> None:
        for controller in hardware.microcontrollers:
            if controller.hardware_system_id not in (None, hardware.id):
                raise ValueError(f"Conflicting hardware system ownership: {controller.name}")
            for connection in controller.connections:
                if connection.microcontroller_id not in (None, controller.id):
                    raise ValueError(f"Conflicting microcontroller ownership: {connection.name}")

    @staticmethod
    def build_state(plan: HardwarePlan) -> HardwareRuntime:
        state = HardwareRuntime()
        for board in plan.boards:
            for connection in board.connections:
                for key in CommandCompiler.state_keys(connection):
                    state.register_state_store(key)
        return state

    @staticmethod
    def generate_firmware(hardware: HardwareSystem) -> dict[str, Path]:
        GerberaRuntime.bind_connection_microcontroller_ids(hardware)
        return {
            board.id: FirmwareGenerator(board).write_files()
            for board in hardware.microcontrollers
        }

    @staticmethod
    def compile_firmware(hardware: HardwareSystem, sketches: dict[str, Path]) -> dict[str, Path]:
        return {
            board.id: FirmwareUploader(board).compile(sketches[board.id])
            for board in hardware.microcontrollers
        }

    @staticmethod
    def upload_firmware(hardware: HardwareSystem, builds: dict[str, Path]) -> None:
        for board in hardware.microcontrollers:
            FirmwareUploader(board).upload(builds[board.id])

    @staticmethod
    def install_dependencies(hardware: HardwareSystem) -> None:
        FirmwareUploader.install_dependencies(hardware)
