from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastmcp import FastMCP

from gerbera_sdk import gerbera_runtime as runtime_module
from gerbera_sdk.gerbera_runtime import GerberaRuntime
from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.database import Database
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import Microcontroller, RuntimeTransportConfig
from gerbera_sdk.models.runtime.storage.database_settings import DatabaseSettings


@pytest.fixture
def hardware():
    return HardwareSystem(
        id="system-1", name="robot", description="Robot description", microcontrollers=[Microcontroller(
            runtime_transport=RuntimeTransportConfig.usb_serial("/dev/test"),
            name="board", device_id="board-1", upload_port="/dev/test", fqbn="arduino:avr:uno",
            connections=[Connection(name="sensor", component_type="hw201", pins={"out": "7"}, description="Sensor")],
        )],
    )


@pytest.fixture
def database():
    return DatabaseSettings("localhost", 5432, "writer", "schema")


def test_facade_binds_declared_connections_to_resolved_identity(hardware) -> None:
    GerberaRuntime.validate_hardware(hardware)

    board = hardware.microcontrollers[0]
    assert (board.hardware_system_id, board.connections[0].microcontroller_id) == ("system-1", "board-1")


def test_database_settings_build_the_writer_role() -> None:
    database = DatabaseSettings("database.internal", 5432, "secret").writer()

    assert database == Database(
        host="database.internal", port=5432, user="gerbera_writer", password="secret", database_name="gerbera",
    )


def test_facade_builds_application_without_starting_external_resources(hardware, database, monkeypatch) -> None:
    start = Mock(side_effect=AssertionError("Application construction must not start resources"))
    monkeypatch.setattr(runtime_module.BoardRuntime, "start", start)
    monkeypatch.setattr(runtime_module.EventWorker, "start", start)
    monkeypatch.setattr(runtime_module.FastMCP, "run", start)
    monkeypatch.setattr("psycopg.connect", start)

    app = GerberaRuntime.build_application(hardware, database)

    assert isinstance(app, FastMCP) and start.call_count == 0


def test_facade_shares_response_registry_between_execution_and_listener(hardware, database, monkeypatch) -> None:
    commands = Mock(wraps=runtime_module.CommandExecutor)
    listener = Mock(wraps=runtime_module.EventListener)
    monkeypatch.setattr(runtime_module, "CommandExecutor", commands)
    monkeypatch.setattr(runtime_module, "EventListener", listener)

    GerberaRuntime.build_application(hardware, database)

    assert commands.call_args.args[2] is listener.call_args.kwargs["command_responses"]


def test_run_uses_the_application_construction_path(hardware, database, monkeypatch) -> None:
    run = Mock()
    build = Mock(return_value=SimpleNamespace(run=run))
    monkeypatch.setattr(GerberaRuntime, "build_application", build)

    GerberaRuntime.run(hardware, database, transport="http", port=8001)

    assert (build.call_args.args, run.call_args.kwargs) == (
        (hardware, database), {"transport": "http", "port": 8001},
    )


def test_firmware_generation_does_not_compile_or_upload(hardware, monkeypatch, tmp_path) -> None:
    sketch = tmp_path / "board.ino"
    generator = Mock(return_value=SimpleNamespace(write_files=lambda: sketch))
    other_stages = Mock(side_effect=AssertionError("Generation must not compile or upload"))
    monkeypatch.setattr(runtime_module, "FirmwareGenerator", generator)
    monkeypatch.setattr(runtime_module, "FirmwareCompiler", other_stages)
    monkeypatch.setattr(runtime_module, "FirmwareUploader", other_stages)

    assert GerberaRuntime.generate_firmware(hardware) == {"board-1": sketch}


def test_firmware_compilation_consumes_the_supplied_sketch(hardware, monkeypatch, tmp_path) -> None:
    sketch = tmp_path / "board.ino"
    build = tmp_path / "build"
    compile_source = Mock(return_value=build)
    monkeypatch.setattr(runtime_module, "FirmwareCompiler", lambda board: SimpleNamespace(compile=compile_source))
    unexpected = Mock(side_effect=AssertionError("Compilation must not generate or upload"))
    monkeypatch.setattr(runtime_module, "FirmwareGenerator", unexpected)
    monkeypatch.setattr(runtime_module, "FirmwareUploader", unexpected)

    result = GerberaRuntime.compile_firmware(hardware, {"board-1": sketch})

    assert (result, compile_source.call_args.args) == ({"board-1": build}, (sketch,))


def test_firmware_upload_consumes_existing_build(hardware, monkeypatch, tmp_path) -> None:
    upload = Mock()
    monkeypatch.setattr(runtime_module, "FirmwareUploader", lambda board: SimpleNamespace(upload=upload))
    unexpected = Mock(side_effect=AssertionError("Upload must not generate or compile"))
    monkeypatch.setattr(runtime_module, "FirmwareGenerator", unexpected)
    monkeypatch.setattr(runtime_module, "FirmwareCompiler", unexpected)

    GerberaRuntime.upload_firmware(hardware, {"board-1": tmp_path})

    assert upload.call_args.args == (tmp_path,)


def test_firmware_verification_propagates_mismatch(hardware, monkeypatch) -> None:
    verify = Mock(side_effect=RuntimeError("firmware mismatch"))
    monkeypatch.setattr(runtime_module, "FirmwareVerifier", lambda boards: SimpleNamespace(verify=verify))
    unexpected = Mock(side_effect=AssertionError("Verification must not upload"))
    monkeypatch.setattr(runtime_module, "FirmwareUploader", unexpected)

    with pytest.raises(RuntimeError, match="firmware mismatch"):
        GerberaRuntime.verify_firmware(hardware)


def test_applications_share_declarations_without_sharing_command_execution(hardware, database, monkeypatch) -> None:
    from gerbera_sdk.models.runtime.boards.serial_protocol import SerialMessageCodec
    from gerbera_sdk.models.runtime.commands.command_executor import CommandExecutor
    from gerbera_sdk.models.runtime.server.tool_registry import McpToolRegistry

    captured = []
    executors = []
    register = McpToolRegistry.register

    def capture(registry, definition):
        captured.append((registry.app, definition))
        register(registry, definition)

    def make_executor(*args):
        executor = CommandExecutor(*args)
        label = "first" if not executors else "second"

        def write(command):
            message = SerialMessageCodec.decode(command)
            executor.responses.resolve(message.fields["command_id"], {"runtime": label})

        executor.boards = SimpleNamespace(get_transport=lambda board_id: SimpleNamespace(write=write))
        executors.append(executor)
        return executor

    monkeypatch.setattr(runtime_module, "CommandExecutor", make_executor)
    monkeypatch.setattr(McpToolRegistry, "register", capture)
    first = GerberaRuntime.build_application(hardware, database)
    second = GerberaRuntime.build_application(hardware, database)
    callbacks = [next(tool.tool_function for app, tool in captured if app is instance and tool.name == "read_sensor")
                 for instance in (first, second)]

    assert [callback()["value"]["runtime"] for callback in callbacks] == ["first", "second"]


def test_application_construction_defers_model_files_movement_files_and_reaction_restore(database, monkeypatch) -> None:
    from gerbera_sdk.inference import ObjectDetectionModel
    from gerbera_sdk.models.hardware.camera import Camera, DeviceCameraSource
    from gerbera_sdk.models.hardware.movement_system import Link, MovementSystem
    from gerbera_sdk.events.reactions.reaction_service import ReactionService

    camera = Camera(name="camera", description="Camera", source=DeviceCameraSource(0))
    model = ObjectDetectionModel(name="detector", model_directory="missing-model-directory", subscribed_camera=camera)
    hardware = HardwareSystem(
        name="robot", cameras=[camera], models=[model],
        movement_systems=[MovementSystem(name="arm", base_link=Link(name="base"))],
    )
    preparation = Mock(side_effect=AssertionError("Preparation must wait for lifecycle startup"))
    monkeypatch.setattr(ObjectDetectionModel, "create_inference", preparation)
    monkeypatch.setattr(runtime_module.MovementRuntime, "write_urdf", preparation)
    monkeypatch.setattr(ReactionService, "restore_reactions", preparation)

    app = GerberaRuntime.build_application(hardware, database)

    assert isinstance(app, FastMCP) and preparation.call_count == 0
