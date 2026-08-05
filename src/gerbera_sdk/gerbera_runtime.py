import subprocess
from typing import Annotated, Literal

from fastmcp import FastMCP
from pydantic import Field, StrictFloat

from gerbera_sdk.contracts.command_contract import CommandSpec
from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event_worker import EventWorker
from gerbera_sdk.events.rules import OperatorEnum, RuleTriggerModeEnum
from gerbera_sdk.events.stream_controller import StreamController
from gerbera_sdk.firmware.flash import Flash
from gerbera_sdk.inference import (
    Inference,
    ObjectDetectionModelInference,
    PerceptionStateModel,
    VisionLanguageModelFrameEnvironment,
)
from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import Microcontroller
from gerbera_sdk.models.runtime.agent_runtime import AgentRuntime
from gerbera_sdk.models.runtime.board_runtime import BoardRuntime
from gerbera_sdk.models.runtime.camera_runtime import CameraRuntime
from gerbera_sdk.models.runtime.command_runtime import CommandCompiler
from gerbera_sdk.models.runtime.database_runtime import DatabaseRuntime
from gerbera_sdk.models.runtime.model_runtime import ModelRuntime
from gerbera_sdk.models.runtime.runtime_lifecycle import RuntimeLifecycle
from gerbera_sdk.models.runtime.server_runtime import (
    EventCatalog,
    ServerRuntime,
)
from gerbera_sdk.utils import StrictSchema


class SubscribedCameraCatalogEntry(StrictSchema):
    camera_id: str
    name: str


class ModelCatalogEntry(StrictSchema):
    model_id: str
    name: str
    description: str
    model_type: Literal["object_detection", "vision_language_model"]
    subscribed_cameras: list[SubscribedCameraCatalogEntry]
    is_running: bool
    turn_on_tool: str
    turn_off_tool: str
    read_tool: str
    single_inference_tool: str


class GerberaRuntime:

    # Driver Code for Setting Up Hardware Connection
    @staticmethod
    def setup(
        hardware_system: HardwareSystem,
        install_dependencies: bool = True,
        flash_firmware: bool = True,
    ) -> None:
        if install_dependencies:
            GerberaRuntime._install_dependencies(hardware_system)

        if flash_firmware:
            Flash.flash(hardware_system)

    # Driver Code for Setting Up Server Connection
    @staticmethod
    def run(
        hardware_system: HardwareSystem,
        transport: str = "stdio",
        mcp_url: str = "",
        **transport_kwargs,
    ) -> None:
        GerberaRuntime._validate_unique_connection_names(hardware_system)
        board_runtime = GerberaRuntime._build_board_runtime(hardware_system)
        camera_runtime = GerberaRuntime._build_camera_runtime(hardware_system)
        event_worker = GerberaRuntime._build_event_worker()
        database_runtime = GerberaRuntime._build_database_runtime(
            hardware_system,
            event_worker,
        )
        model_runtime = GerberaRuntime._build_model_runtime(hardware_system)
        runtime_lifecycle = RuntimeLifecycle(
            board_runtime=board_runtime,
            camera_runtime=camera_runtime,
            database_runtime=database_runtime,
            model_runtime=model_runtime,
        )
        server_runtime = GerberaRuntime._build_server_runtime(
            hardware_system=hardware_system,
            board_runtime=board_runtime,
            event_worker=event_worker,
            runtime_lifecycle=runtime_lifecycle,
        )
        server_runtime.agent_runtime = GerberaRuntime._build_agent_runtime(
            server_runtime=server_runtime,
            mcp_url=mcp_url,
        )

        server_runtime._register_events()
        GerberaRuntime._register_server_runtime_tools(server_runtime)
        GerberaRuntime._register_agent_runtime_tool(server_runtime)
        GerberaRuntime._register_event_catalog_tool(server_runtime)
        server_runtime.app.run(
            transport=transport,
            **transport_kwargs,
        )

    @staticmethod
    def _validate_unique_connection_names(
        hardware_system: HardwareSystem,
    ) -> None:
        connection_owners: dict[str, str] = {}

        for microcontroller in hardware_system.microcontrollers:
            for connection in microcontroller.connections:
                normalized_name = connection.name.strip().lower()
                if not normalized_name:
                    raise ValueError("Connection name cannot be empty")

                existing_owner = connection_owners.get(normalized_name)
                if existing_owner is not None:
                    raise ValueError(
                        f"Connection name must be globally unique: {connection.name}. "
                        f"Used by microcontrollers {existing_owner} and "
                        f"{microcontroller.id}"
                    )

                connection_owners[normalized_name] = microcontroller.id

    @staticmethod
    def _build_board_runtime(
        hardware_system: HardwareSystem,
    ) -> BoardRuntime:
        return BoardRuntime(hardware_system=hardware_system)

    @staticmethod
    def _build_camera_runtime(
        hardware_system: HardwareSystem,
    ) -> CameraRuntime:
        return CameraRuntime(hardware_system=hardware_system)

    @staticmethod
    def _build_model_runtime(
        hardware_system: HardwareSystem,
    ) -> ModelRuntime:
        return ModelRuntime(hardware_system=hardware_system)

    @staticmethod
    def _build_server_runtime(
        hardware_system: HardwareSystem,
        board_runtime: BoardRuntime,
        event_worker: EventWorker,
        runtime_lifecycle: RuntimeLifecycle,
    ) -> ServerRuntime:
        event_bus = EventBus()
        stream_controller = StreamController(event_bus)
        app = FastMCP(
            hardware_system.description,
            lifespan=runtime_lifecycle,
        )

        server_runtime = ServerRuntime(
            hardware_system=hardware_system,
            board_runtime=board_runtime,
            event_bus=event_bus,
            stream_controller=stream_controller,
            event_worker=event_worker,
            app=app,
            camera_runtime=runtime_lifecycle.camera_runtime,
            model_runtime=runtime_lifecycle.model_runtime,
        )
        runtime_lifecycle.bind_server_runtime(server_runtime)
        return server_runtime

    @staticmethod
    def _build_event_worker() -> EventWorker:
        return EventWorker()

    @staticmethod
    def _build_agent_runtime(
        server_runtime: ServerRuntime,
        mcp_url: str,
    ) -> AgentRuntime:
        return AgentRuntime(
            mcp_url=mcp_url,
            rule_bus=server_runtime.rule_bus,
            rule_buffer=server_runtime.rule_buffer,
            valid_event_keys=server_runtime.event_bus.events,
        )

    @staticmethod
    def _build_database_runtime(
        hardware_system: HardwareSystem,
        event_worker: EventWorker,
    ) -> DatabaseRuntime:
        return DatabaseRuntime(
            hardware_system=hardware_system,
            event_worker=event_worker,
        )

    @staticmethod
    def _connection_supports_state_toggle(connection: Connection) -> bool:
        for command in CommandCompiler.command_specs(connection):
            if GerberaRuntime._command_is_state_toggle(command):
                return True

        return False

    @staticmethod
    def _command_is_state_toggle(command: CommandSpec) -> bool:
        if command.method.strip().upper() != "WRITE":
            return False

        state_param = command.params.get("state")
        return state_param is not None and {"on", "off"}.issubset(
            set(state_param.enum)
        )

    @staticmethod
    def _connection_supports_stream_toggle(connection: Connection) -> bool:
        return (
            connection.database is not None
            and GerberaRuntime._connection_supports_state_toggle(connection)
        )

    @staticmethod
    def _register_server_runtime_tools(server_runtime: ServerRuntime) -> None:
        for microcontroller in server_runtime.hardware_system.microcontrollers:
            for connection in microcontroller.connections:
                GerberaRuntime._register_connection_tools(
                    server_runtime=server_runtime,
                    microcontroller=microcontroller,
                    connection=connection,
                )

        GerberaRuntime._register_camera_tools(server_runtime)
        GerberaRuntime._register_inference_tools(server_runtime)

    @staticmethod
    def _register_camera_tools(
        server_runtime: ServerRuntime,
    ) -> None:
        cameras = server_runtime.hardware_system.cameras
        if not cameras:
            return

        camera_runtime = server_runtime.camera_runtime
        if camera_runtime is None:
            raise RuntimeError("Camera runtime is not configured")

        for camera in cameras:
            camera_key = camera.camera_id

            def build_capture_frames_tool(camera_key: str):
                def capture_frames_from_camera(
                    image_count: Annotated[
                        int,
                        Field(ge=1, le=20),
                    ] = 1,
                    interval_seconds: Annotated[
                        float,
                        Field(ge=0.0, le=60.0),
                    ] = 0.0,
                ) -> list[str]:
                    frames = camera_runtime.capture_frames(
                        camera_key=camera_key,
                        image_count=image_count,
                        interval_seconds=interval_seconds,
                    )
                    return [frame.to_base64_string() for frame in frames]

                return capture_frames_from_camera

            server_runtime._register_tool(
                name=f"capture_frames_from_{camera.name}",
                description=(
                    f"Capture one or more current images from {camera.name}. "
                    "image_count controls the batch size and interval_seconds "
                    "controls the delay between images. Returns the images as "
                    "Base64 strings for precise vision inference."
                ),
                tool_function=build_capture_frames_tool(camera_key),
            )

    @staticmethod
    def _register_inference_tools(
        server_runtime: ServerRuntime,
    ) -> None:
        model_runtime = server_runtime.model_runtime
        if model_runtime is None:
            if server_runtime.hardware_system.models:
                raise RuntimeError("Model runtime is not configured")
            return

        registered_models: dict[str, tuple[str, Inference]] = {}

        for model_id, inference in model_runtime.model_inferences.items():
            registered_model = registered_models.get(inference.name)
            if registered_model is not None:
                raise ValueError(
                    f"Inference model name must be unique: {inference.name}"
                )
            registered_models[inference.name] = (model_id, inference)

        for model_id, model in registered_models.values():
            def build_turn_on_inference_tool(model_id: str):
                def turn_on_inference() -> None:
                    model_runtime.turn_on_model(model_id)

                return turn_on_inference

            turn_on_tool_name = f"turn_on_{model.name}"
            turn_off_tool_name = f"turn_off_{model.name}"
            read_tool_name = f"read_{model.name}"
            single_inference_tool_name = f"perform_single_{model.name}"

            server_runtime._register_tool(
                name=turn_on_tool_name,
                description=f"Start continuous inference for {model.name}.",
                tool_function=build_turn_on_inference_tool(model_id),
            )

            def build_turn_off_inference_tool(model_id: str):
                def turn_off_inference() -> None:
                    model_runtime.turn_off_model(model_id)

                return turn_off_inference

            server_runtime._register_tool(
                name=turn_off_tool_name,
                description=f"Stop continuous inference for {model.name}.",
                tool_function=build_turn_off_inference_tool(model_id),
            )

            if isinstance(model, ObjectDetectionModelInference):
                def build_read_tool(model_id: str):
                    def read_model_output(
                        camera_id: str,
                    ) -> dict[str, object]:
                        result = model_runtime.read_model_output(
                            model_id,
                            camera_id,
                        )
                        if not isinstance(result, PerceptionStateModel):
                            raise TypeError(
                                "Object detection stored an invalid result"
                            )
                        return result.model_dump(
                            mode="json",
                            exclude={"frame"},
                        )

                    return read_model_output

                def build_predict_tool(model_id: str):
                    def predict_with_model(
                        camera_ids: Annotated[
                            list[str],
                            Field(min_length=1),
                        ],
                    ) -> list[dict[str, object]]:
                        results = model_runtime.single_inference(
                            model_id,
                            camera_ids,
                        )
                        if not isinstance(results, list) or not all(
                            isinstance(result, PerceptionStateModel)
                            for result in results
                        ):
                            raise TypeError(
                                "Object detection returned an invalid result"
                            )
                        return [
                            result.model_dump(
                                mode="json",
                                exclude={"frame"},
                            )
                            for result in results
                        ]

                    return predict_with_model

                read_tool = build_read_tool(model_id)
                predict_tool = build_predict_tool(model_id)
                predict_description = (
                    f"{model.description} Provide one or more IDs of "
                    "subscribed cameras with current frames."
                )
            else:
                def build_read_tool(model_id: str):
                    def read_model_output(
                        camera_id: str,
                    ) -> VisionLanguageModelFrameEnvironment:
                        result = model_runtime.read_model_output(
                            model_id,
                            camera_id,
                        )
                        if not isinstance(
                            result,
                            VisionLanguageModelFrameEnvironment,
                        ):
                            raise TypeError(
                                "Vision language model stored an invalid result"
                            )
                        return result

                    return read_model_output

                def build_predict_tool(model_id: str):
                    def predict_with_model(
                        frames: Annotated[
                            list[str],
                            Field(min_length=1),
                        ],
                    ) -> VisionLanguageModelFrameEnvironment:
                        return model_runtime.single_inference(
                            model_id,
                            frames,
                        )

                    return predict_with_model

                read_tool = build_read_tool(model_id)
                predict_tool = build_predict_tool(model_id)
                predict_description = (
                    f"{model.description} Provide one or more Base64 "
                    "image strings."
                )

            server_runtime._register_tool(
                name=read_tool_name,
                description=(
                    f"Read the latest continuous inference output from "
                    f"{model.name} for a subscribed camera ID."
                ),
                tool_function=read_tool,
            )

            server_runtime._register_tool(
                name=single_inference_tool_name,
                description=predict_description,
                tool_function=predict_tool,
            )

        def list_configured_models() -> list[ModelCatalogEntry]:
            catalog: list[ModelCatalogEntry] = []
            for model_id, model in registered_models.values():
                model_type = (
                    "object_detection"
                    if isinstance(model, ObjectDetectionModelInference)
                    else "vision_language_model"
                )
                catalog.append(
                    ModelCatalogEntry(
                        model_id=model_id,
                        name=model.name,
                        description=model.description,
                        model_type=model_type,
                        subscribed_cameras=[
                            SubscribedCameraCatalogEntry(
                                camera_id=camera.camera_id,
                                name=camera.name,
                            )
                            for camera in model.subscribed_cameras
                        ],
                        is_running=model.is_running,
                        turn_on_tool=f"turn_on_{model.name}",
                        turn_off_tool=f"turn_off_{model.name}",
                        read_tool=f"read_{model.name}",
                        single_inference_tool=(
                            f"perform_single_{model.name}"
                        ),
                    )
                )
            return catalog

        server_runtime._register_tool(
            name="list_configured_models",
            description=(
                "List configured inference models, their model IDs, "
                "subscribed camera IDs, current running state, and exact "
                "lifecycle, read, and single-inference tool names."
            ),
            tool_function=list_configured_models,
        )

    @staticmethod
    def _register_agent_runtime_tool(
        server_runtime: ServerRuntime,
    ) -> None:
        agent_runtime = server_runtime.agent_runtime
        if agent_runtime is None:
            raise RuntimeError("Agent runtime is not configured")

        def insert_rule(
            event_type: str,
            microcontroller_id: str,
            event_name: str,
            expected_value: Annotated[
                StrictFloat,
                Field(allow_inf_nan=False),
            ],
            operator: OperatorEnum,
            callback_body: str,
            trigger_mode: RuleTriggerModeEnum = RuleTriggerModeEnum.REPEAT,
        ) -> dict[str, str]:
            return agent_runtime.insert_rule(
                event_type=event_type,
                microcontroller_id=microcontroller_id,
                event_name=event_name,
                expected_value=expected_value,
                operator=operator,
                callback_body=callback_body,
                trigger_mode=trigger_mode,
            )

        server_runtime._register_tool(
            name="insert_rule",
            description=(
                "Create and register a rule for a hardware event. "
                "callback_body must contain only the Python statements for "
                "async callback(mcp_url, value). The runtime imports httpx "
                "and fastmcp.Client, adds the fixed function definition, and "
                "binds the configured MCP URL and finite-float sensor value. "
                "The agent must use the mcp_url parameter and must not provide "
                "or hardcode an endpoint."
            ),
            tool_function=insert_rule,
        )

        def delete_rule(
            event_type: str,
            microcontroller_id: str,
            event_name: str,
        ) -> dict[str, str]:
            return agent_runtime.delete_rule(
                event_type=event_type,
                microcontroller_id=microcontroller_id,
                event_name=event_name,
            )

        server_runtime._register_tool(
            name="delete_rule",
            description=(
                "Delete the rule registered for a hardware event and remove "
                "its local callback script."
            ),
            tool_function=delete_rule,
        )

    @staticmethod
    def _register_event_catalog_tool(
        server_runtime: ServerRuntime,
    ) -> None:
        def list_rule_events() -> EventCatalog:
            return server_runtime.get_event_catalog()

        server_runtime._register_tool(
            name="list_rule_events",
            description=(
                "List the registered hardware events that can be used "
                "when creating rules."
            ),
            tool_function=list_rule_events,
        )

    @staticmethod
    def _register_connection_tools(
        server_runtime: ServerRuntime,
        microcontroller: Microcontroller,
        connection: Connection,
    ) -> None:
        supports_stream_toggle = (
            GerberaRuntime._connection_supports_stream_toggle(connection)
        )
        for command in CommandCompiler.command_specs(connection):
            server_runtime._register_connection_action(
                microcontroller,
                connection,
                command,
            )
            if not (
                supports_stream_toggle
                and GerberaRuntime._command_is_state_toggle(command)
            ):
                server_runtime._register_connection_tool(connection, command)

        if supports_stream_toggle:
            server_runtime._register_stream_toggle_tools(
                microcontroller,
                connection,
            )
        elif GerberaRuntime._connection_supports_state_toggle(connection):
            server_runtime._register_state_toggle_tools(connection)

    @staticmethod
    def _install_dependencies(hardware_system: HardwareSystem) -> None:
        for package_name in hardware_system._get_required_microcontroller_libraries():
            subprocess.run(
                ["arduino-cli", "core", "install", package_name],
                check=True,
            )

        installed_libraries: set[str] = set()
        for microcontroller in hardware_system.microcontrollers:
            for library in microcontroller._get_required_connection_libraries():
                install_name = library.install.strip()
                normalized_install_name = install_name.lower()

                if not install_name or normalized_install_name in installed_libraries:
                    continue

                subprocess.run(
                    ["arduino-cli", "lib", "install", install_name],
                    check=True,
                )
                installed_libraries.add(normalized_install_name)
