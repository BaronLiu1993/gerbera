import os
import asyncio

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event_listener import EventListener
from gerbera_sdk.events.event_worker import EventWorker
from gerbera_sdk.events.reactions.reaction_bus import ReactionBus
from gerbera_sdk.firmware.reconciliation import FirmwareDependencies, FirmwareReconciler
from gerbera_sdk.models.hardware.database import Database
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.hardware_plan import HardwarePlan
from gerbera_sdk.models.hardware.validation import HardwareContractCompiler
from gerbera_sdk.models.runtime.board_runtime import BoardRuntime
from gerbera_sdk.models.runtime.camera_runtime import CameraRuntime
from gerbera_sdk.models.runtime.command_runtime import CommandCompiler
from gerbera_sdk.models.runtime.command_acknowledgement import (
    CommandAcknowledgementRegistry,
)
from gerbera_sdk.models.runtime.model_runtime import ModelRuntime
from gerbera_sdk.models.runtime.runtime_lifecycle import RuntimeLifecycle
from gerbera_sdk.models.runtime.server_runtime import ServerRuntime
from gerbera_sdk.models.runtime.hardware_runtime import HardwareRuntime
from gerbera_sdk.models.runtime.movement_runtime import MovementRuntime
from gerbera_sdk.models.runtime.readiness import RuntimeReadiness
from gerbera_sdk.models.runtime.storage import RuntimeStorage


class GerberaRuntime:
    @staticmethod
    def setup(
        hardware_system: HardwareSystem,
    ) -> None:
        GerberaRuntime.bind_connection_microcontroller_ids(hardware_system)
        hardware_plan = GerberaRuntime.validate_hardware(hardware_system)

        FirmwareReconciler(BoardRuntime(hardware_plan)).reconcile()

    @staticmethod
    def run(
        hardware_system: HardwareSystem,
        transport: str,
        database_host: str,
        database_port: int,
        database_password: str,
        database_schema_password: str | None = None,
        **transport_kwargs,
    ) -> None:
        GerberaRuntime.bind_connection_microcontroller_ids(hardware_system)
        hardware_plan = GerberaRuntime.validate_hardware(hardware_system)

        database = GerberaRuntime.runtime_database(
            host=database_host,
            port=database_port,
            password=database_password,
        )
        board_runtime = BoardRuntime(hardware_plan)
        camera_runtime = CameraRuntime(hardware_system)
        event_worker = EventWorker(database=database)
        model_runtime = ModelRuntime(
            hardware_system=hardware_system,
            camera_runtime=camera_runtime,
        )
        hardware_runtime = HardwareRuntime()
        movement_runtime = None
        if hardware_system.movement_systems:
            movement_runtime = MovementRuntime(hardware_system)
            movement_runtime.register_movement_system()

        GerberaRuntime.register_connection_states(
            hardware_plan=hardware_plan,
            hardware_runtime=hardware_runtime,
        )

        event_bus = EventBus()
        reaction_bus = ReactionBus()
        command_acknowledgements = CommandAcknowledgementRegistry()
        event_listener = EventListener(
            hardware_plan=hardware_plan,
            transport_pool=board_runtime.transport_pool,
            event_bus=event_bus,
            reaction_bus=reaction_bus,
            hardware_runtime=hardware_runtime,
            command_acknowledgements=command_acknowledgements,
            reconnect_board=board_runtime.reconnect_board,
        )
        readiness = RuntimeReadiness(
            board_runtime, camera_runtime, model_runtime, event_listener, event_worker,
        )
        schema_password = database_schema_password or os.environ.get("GERBERA_SCHEMA_PASSWORD")
        schema_owner = None
        if schema_password:
            schema_owner = Database(
                host=database_host, port=database_port, password=schema_password,
                user="gerbera_schema_owner", database_name="gerbera",
            )
        runtime_lifecycle = RuntimeLifecycle(
            board_runtime=board_runtime,
            camera_runtime=camera_runtime,
            event_worker=event_worker,
            model_runtime=model_runtime,
            event_listener=event_listener,
            event_bus=event_bus,
            hardware_runtime=hardware_runtime,
            movement_runtime=movement_runtime,
            storage=RuntimeStorage(hardware_plan, database, schema_owner),
            readiness=readiness,
        )
        app = FastMCP(
            hardware_system.description,
            lifespan=runtime_lifecycle,
        )

        @app.custom_route("/health", methods=["GET"])
        async def health(request: Request) -> JSONResponse:
            return JSONResponse({"service": "sdk", "status": "alive"})

        @app.custom_route("/ready", methods=["GET"])
        async def ready(request: Request) -> JSONResponse:
            report = await asyncio.to_thread(readiness.snapshot)
            return JSONResponse(report.model_dump(mode="json"), status_code=200 if report.ready else 503)

        @app.resource("gerbera://readiness", mime_type="application/json")
        def runtime_readiness() -> str:
            return readiness.snapshot().model_dump_json()
        server_runtime = ServerRuntime(
            hardware_system=hardware_system,
            hardware_plan=hardware_plan,
            board_runtime=board_runtime,
            event_bus=event_bus,
            event_worker=event_worker,
            app=app,
            camera_runtime=camera_runtime,
            model_runtime=model_runtime,
            event_listener=event_listener,
            reaction_bus=reaction_bus,
            hardware_runtime=hardware_runtime,
            command_acknowledgements=command_acknowledgements,
            movement_runtime=movement_runtime,
        )

        server_runtime.register_events()
        server_runtime.register_tools()
        app.run(transport=transport, **transport_kwargs)

    @staticmethod
    def validate_hardware(
        hardware_system: HardwareSystem,
    ) -> HardwarePlan:
        return HardwareContractCompiler.compile(hardware_system)

    @staticmethod
    def bind_connection_microcontroller_ids(
        hardware_system: HardwareSystem,
    ) -> None:
        hardware_system_id = hardware_system.id
        for microcontroller in hardware_system.microcontrollers:
            microcontroller.hardware_system_id = hardware_system_id
            microcontroller_id = microcontroller.id
            for connection in microcontroller.connections:
                connection.microcontroller_id = microcontroller_id

    @staticmethod
    def register_connection_states(
        hardware_plan: HardwarePlan,
        hardware_runtime: HardwareRuntime,
    ) -> None:
        for board in hardware_plan.boards:
            for connection in board.connections:
                for key in CommandCompiler.state_keys(connection):
                    hardware_runtime.register_state_store(key)

    @staticmethod
    def runtime_database(
        host: str,
        port: int,
        password: str,
    ) -> Database:
        return Database(
            host=host,
            port=port,
            password=password,
            user="gerbera_writer",
            database_name="gerbera",
        )

    @staticmethod
    def install_dependencies(hardware_system: HardwareSystem) -> None:
        GerberaRuntime.bind_connection_microcontroller_ids(hardware_system)
        FirmwareDependencies(GerberaRuntime.validate_hardware(hardware_system)).install()
