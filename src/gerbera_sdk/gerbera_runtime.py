from pathlib import Path

from fastmcp import FastMCP

from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event_listener import EventListener
from gerbera_sdk.events.event_registration import EventRegistration
from gerbera_sdk.events.event_worker import EventWorker
from gerbera_sdk.events.reactions.reaction_bus import ReactionBus
from gerbera_sdk.events.reactions.reaction_executor import ReactionToolRegistry
from gerbera_sdk.events.reactions.reaction_service import ReactionService
from gerbera_sdk.firmware.firmware_compiler import FirmwareCompiler
from gerbera_sdk.firmware.firmware_dependencies import FirmwareDependencies
from gerbera_sdk.firmware.firmware_generator import FirmwareGenerator
from gerbera_sdk.firmware.firmware_uploader import FirmwareUploader
from gerbera_sdk.firmware.firmware_verifier import FirmwareVerifier
from gerbera_sdk.models.hardware.hardware_plan import HardwarePlan
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.validation import HardwareContractCompiler
from gerbera_sdk.models.runtime.boards.board_runtime import BoardRuntime
from gerbera_sdk.models.runtime.commands.connection_control import ConnectionControl
from gerbera_sdk.models.runtime.commands.command_executor import CommandExecutor
from gerbera_sdk.models.runtime.commands.command_response import CommandResponseRegistry
from gerbera_sdk.models.runtime.commands.command_runtime import CommandCompiler
from gerbera_sdk.models.runtime.movement.movement_runtime import MovementRuntime
from gerbera_sdk.models.runtime.perception.camera_runtime import CameraRuntime
from gerbera_sdk.models.runtime.perception.model_runtime import ModelRuntime
from gerbera_sdk.models.runtime.server.hardware_tools import HardwareTools
from gerbera_sdk.models.runtime.server.health_routes import HealthRoutes
from gerbera_sdk.models.runtime.server.movement_tools import MovementTools
from gerbera_sdk.models.runtime.server.perception_tools import PerceptionTools
from gerbera_sdk.models.runtime.server.readiness import RuntimeReadiness
from gerbera_sdk.models.runtime.server.reaction_tools import ReactionTools
from gerbera_sdk.models.runtime.server.runtime_lifecycle import RuntimeLifecycle
from gerbera_sdk.models.runtime.server.runtime_resources import RuntimeResources
from gerbera_sdk.models.runtime.server.server_runtime import ServerRuntime
from gerbera_sdk.models.runtime.server.tool_registry import McpToolRegistry
from gerbera_sdk.models.runtime.state.hardware_runtime import HardwareRuntime
from gerbera_sdk.models.runtime.storage.database_settings import DatabaseSettings
from gerbera_sdk.models.runtime.storage.storage import RuntimeStorage


class GerberaRuntime:
    @staticmethod
    def build_application(hardware: HardwareSystem, database: DatabaseSettings) -> FastMCP:
        plan = GerberaRuntime.validate_hardware(hardware)
        boards = BoardRuntime(plan)
        cameras = CameraRuntime(hardware)
        models = ModelRuntime(hardware, cameras)
        models.register_models()
        writer = database.writer()
        worker = EventWorker(database=writer)
        state = GerberaRuntime.build_state(plan)
        events = EventBus()
        EventRegistration(plan, events, worker).register()
        responses = CommandResponseRegistry()
        commands = CommandExecutor(plan, boards, responses)
        commands.bind_actions()
        actions = ReactionToolRegistry()
        reaction_bus = ReactionBus(action_executor=actions)
        reactions = ReactionService(plan, events, reaction_bus, actions)
        listener = EventListener(
            hardware_plan=plan, transport_pool=boards.transport_pool,
            event_bus=events, reaction_bus=reaction_bus, hardware_runtime=state,
            command_responses=responses, reconnect_board=boards.reconnect_board,
        )
        movement = GerberaRuntime.build_movement(hardware)
        readiness = RuntimeReadiness(
            sources=(boards, cameras, models, listener, worker), instance_id=hardware.id,
        )
        lifecycle = RuntimeLifecycle(
            board_runtime=boards, camera_runtime=cameras, model_runtime=models,
            event_worker=worker, event_listener=listener, event_bus=events,
            hardware_runtime=state, movement_runtime=movement,
            storage=RuntimeStorage(plan, writer, database.schema_owner()),
            readiness=readiness,
        )
        app = FastMCP(hardware.description or hardware.name, lifespan=lifecycle)
        tools = McpToolRegistry(app, actions)
        server = ServerRuntime(
            resources=RuntimeResources(tools, app, hardware, plan, listener, state, models),
            hardware=HardwareTools(tools, plan, state, ConnectionControl(events, worker, state)),
            perception=PerceptionTools(tools, hardware, cameras, models),
            movement=MovementTools(tools, movement),
            reactions=ReactionTools(tools, reactions),
        )
        HealthRoutes(app, readiness).register()
        server.register_tools()
        return app

    @staticmethod
    def run(hardware: HardwareSystem, database: DatabaseSettings, **transport_options) -> None:
        GerberaRuntime.build_application(hardware, database).run(**transport_options)

    @staticmethod
    def setup(hardware: HardwareSystem) -> None:
        GerberaRuntime.verify_firmware(hardware)

    @staticmethod
    def validate_hardware(hardware: HardwareSystem) -> HardwarePlan:
        GerberaRuntime.bind_connection_microcontroller_ids(hardware)
        return HardwareContractCompiler.compile(hardware)

    @staticmethod
    def bind_connection_microcontroller_ids(hardware: HardwareSystem) -> None:
        for controller in hardware.microcontrollers:
            controller.hardware_system_id = hardware.id
            controller_id = controller.id
            for connection in controller.connections:
                connection.microcontroller_id = controller_id

    @staticmethod
    def build_state(plan: HardwarePlan) -> HardwareRuntime:
        state = HardwareRuntime()
        for board in plan.boards:
            for connection in board.connections:
                for key in CommandCompiler.state_keys(connection):
                    state.register_state_store(key)
        return state

    @staticmethod
    def build_movement(hardware: HardwareSystem) -> MovementRuntime | None:
        if not hardware.movement_systems:
            return None
        movement = MovementRuntime(hardware)
        movement.register_movement_system()
        return movement

    @staticmethod
    def generate_firmware(hardware: HardwareSystem) -> dict[str, Path]:
        return {
            board.microcontroller_id: FirmwareGenerator(board).write_files()
            for board in GerberaRuntime.validate_hardware(hardware).boards
        }

    @staticmethod
    def compile_firmware(hardware: HardwareSystem, sketches: dict[str, Path]) -> dict[str, Path]:
        return {
            board.microcontroller_id: FirmwareCompiler(board).compile(sketches[board.microcontroller_id])
            for board in GerberaRuntime.validate_hardware(hardware).boards
        }

    @staticmethod
    def upload_firmware(hardware: HardwareSystem, builds: dict[str, Path]) -> None:
        for board in GerberaRuntime.validate_hardware(hardware).boards:
            FirmwareUploader(board).upload(builds[board.microcontroller_id])

    @staticmethod
    def verify_firmware(hardware: HardwareSystem) -> None:
        FirmwareVerifier(BoardRuntime(GerberaRuntime.validate_hardware(hardware))).verify()

    @staticmethod
    def install_dependencies(hardware: HardwareSystem) -> None:
        FirmwareDependencies(GerberaRuntime.validate_hardware(hardware)).install()
