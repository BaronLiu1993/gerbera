# Server runtime registers MCP tools and wires hardware events into the app.

from dataclasses import dataclass
from inspect import Parameter, Signature
import time
from typing import Annotated, Any, Callable, Literal

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field, StrictFloat

from gerbera_sdk.contracts.command_contract import CommandSpec, ParameterSpec
from gerbera_sdk.contracts.tool_contract import ToolStage, stage_metadata
from gerbera_sdk.events.event import Event
from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event_listener import EventListener
from gerbera_sdk.events.event_worker import EventWorker
from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import Microcontroller
from gerbera_sdk.models.runtime.board_runtime import BoardRuntime
from gerbera_sdk.models.runtime.camera_runtime import CameraRuntime
from gerbera_sdk.models.runtime.command_runtime import CommandCompiler
from gerbera_sdk.models.runtime.model_runtime import ModelRuntime
from gerbera_sdk.models.runtime.agent_runtime import AgentRuntime
from gerbera_sdk.events.reactions.reaction_store import ReactionBuffer
from gerbera_sdk.events.reactions.reaction_bus import ReactionBus
from gerbera_sdk.events.reactions import OperatorEnum, ReactionTriggerModeEnum
from gerbera_sdk.inference import (
    Inference,
    ObjectDetectionModelInference,
    VisionLanguageModelFrameEnvironment,
)
from gerbera_sdk.utils import StrictSchema

EventMetadata = dict[str, str | bool]
EventCatalog = dict[
    str,
    dict[str, dict[str, EventMetadata]],
]


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


@dataclass
class ServerRuntime:
    hardware_system: HardwareSystem
    board_runtime: BoardRuntime
    event_bus: EventBus
    event_worker: EventWorker
    app: FastMCP
    camera_runtime: CameraRuntime
    model_runtime: ModelRuntime
    agent_runtime: AgentRuntime
    event_listener: EventListener
    reaction_bus: ReactionBus
    reaction_buffer: ReactionBuffer
    event_read_timeout_seconds: float = 1.0
    event_read_poll_seconds: float = 0.02

    def register_tools(self) -> None:
        self._register_hardware_tools()
        self._register_reaction_tools()
        self._register_event_catalog_tool()

    # Event registration and catalog helpers.

    def _register_mcp_event(
        self,
        microcontroller: Microcontroller,
        connection: Connection,
    ) -> None:
        event = Event(
            event_type="MCP",
            microcontroller_id=microcontroller.id,
            event_name=connection.event_name,
            streamable=False,
            table_name=connection.event_name,
            event_worker=self.event_worker,
            latest_val=None,
        )
        self.event_bus.write_event(
            "MCP",
            microcontroller.id,
            connection.event_name,
            event,
        )

    def _register_stream_event(
        self,
        microcontroller: Microcontroller,
        connection: Connection,
    ) -> None:
        if not connection.stream_enabled:
            return

        event = Event(
            event_type="STREAM",
            microcontroller_id=microcontroller.id,
            event_name=connection.event_name,
            streamable=True,
            table_name=connection.event_name,
            event_worker=self.event_worker,
            latest_val=None,
        )
        self.event_bus.write_event(
            "STREAM",
            microcontroller.id,
            connection.event_name,
            event,
        )

    def _register_events(self) -> None:
        for microcontroller in self.hardware_system.microcontrollers:
            for connection in microcontroller.connections:
                self._register_mcp_event(microcontroller, connection)
                self._register_stream_event(microcontroller, connection)

    def get_event_catalog(self) -> EventCatalog:
        connections: dict[tuple[str, str], Connection] = {}
        for microcontroller in self.hardware_system.microcontrollers:
            for connection in microcontroller.connections:
                key = (microcontroller.id, connection.event_name)
                connections[key] = connection
        catalog: EventCatalog = {}

        for event_key, event in self.event_bus.events.items():
            event_type, microcontroller_id, event_name = event_key
            connection = connections[(microcontroller_id, event_name)]
            metadata: EventMetadata = {
                "event_type": event_type,
                "microcontroller_id": microcontroller_id,
                "event_name": event_name,
                "connection_name": connection.name,
                "component_type": connection.component_type,
                "description": connection.description,
                "streamable": event.streamable,
            }
            catalog.setdefault(event_type, {}).setdefault(
                microcontroller_id,
                {},
            )[event_name] = metadata

        return catalog

    # Connection command dispatch and MCP tool generation.

    def _read_latest_event_value(
        self,
        event_key: tuple[str, str, str],
        previous_value: dict[str, str] | None,
    ) -> dict[str, str] | None:
        deadline = time.monotonic() + self.event_read_timeout_seconds
        while time.monotonic() < deadline:
            event = self.event_bus.get_event(*event_key)
            latest_value = event.read_latest()
            if latest_value is not None and latest_value is not previous_value:
                return latest_value

            time.sleep(self.event_read_poll_seconds)

        return None

    def _send_connection_command(
        self,
        microcontroller: Microcontroller,
        connection: Connection,
        action: str,
        params: dict[str, object],
    ) -> dict[str, str] | None:
        serial_connection = self.board_runtime.get_serial_connection(
            microcontroller
        )
        built_command = CommandCompiler.build_command(
            connection,
            action=action,
            params=params,
        )

        event_key = ("MCP", microcontroller.id, connection.event_name)
        previous_value = self.event_bus.get_event(*event_key).read_latest()

        serial_connection.write(built_command)
        return self._read_latest_event_value(event_key, previous_value)

    def _register_connection_action(
        self,
        microcontroller: Microcontroller,
        connection: Connection,
        command: CommandSpec,
    ) -> None:
        action = command.method.strip().upper()

        def action_function(
            params: dict[str, object],
        ) -> dict[str, str] | None:
            return self._send_connection_command(
                microcontroller=microcontroller,
                connection=connection,
                action=action,
                params=params,
            )

        connection.register_action(action, action_function)

    def _build_tool_function(
        self,
        connection: Connection,
        command: CommandSpec,
    ) -> Callable[..., dict[str, str] | None]:
        action = command.method.strip().upper()
        if not command.params:

            def tool_function() -> dict[str, str] | None:
                return connection.perform_action(action, {})

            return tool_function

        def tool_function(**values: Any) -> dict[str, str] | None:
            return connection.perform_action(action, values)

        parameters: list[Parameter] = []
        annotations: dict[str, Any] = {"return": dict[str, str] | None}
        for name, parameter in command.params.items():
            annotation = self._build_parameter_annotation(parameter)
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
            return_annotation=dict[str, str] | None,
        )
        return tool_function

    def _build_parameter_annotation(
        self,
        parameter: ParameterSpec,
    ) -> Any:
        return Annotated[
            float,
            Field(
                description=parameter.description or None,
                ge=parameter.min,
                le=parameter.max,
            ),
        ]

    def _build_stream_toggle_tool_function(
        self,
        microcontroller: Microcontroller,
        connection: Connection,
        state: int,
    ) -> Callable[[], dict[str, str]]:
        def tool_function() -> dict[str, str]:
            response = connection.perform_action("WRITE", {"state": state})

            if state == 0:
                stream_event = self.event_bus.get_event(
                    "STREAM",
                    microcontroller.id,
                    connection.event_name,
                )
                stream_event.flush()
                self.event_worker.wait_until_idle()

            return response

        return tool_function

    def _build_state_toggle_tool_function(
        self,
        connection: Connection,
        state: int,
    ) -> Callable[[], dict[str, str]]:
        def tool_function() -> dict[str, str]:
            return connection.perform_action("WRITE", {"state": state})

        return tool_function

    def _register_connection_tool(
        self,
        connection: Connection,
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
                f" Collected data is stored in table "
                f"`{connection.event_name}`."
            )

        action = command.method.strip().lower()
        tool_name = f"{action}_{connection.name}"
        tool_function = self._build_tool_function(
            connection,
            command,
        )
        self._register_tool(
            name=tool_name,
            description=description,
            tool_function=tool_function,
            annotations=annotations,
        )

    def _register_tool(
        self,
        name: str,
        description: str,
        tool_function: Callable[..., Any],
        annotations: ToolAnnotations,
        meta: dict[str, Any] | None = None,
    ) -> None:
        tool_function.__name__ = name
        tool_function.__doc__ = description
        self.app.tool(
            name=name,
            description=description,
            annotations=annotations,
            meta=meta,
        )(tool_function)

    # On/off tool helpers for stateful and streamable devices.

    def _register_state_toggle_tool(
        self,
        connection: Connection,
        state: int,
        tool_name: str,
        description: str,
        annotations: ToolAnnotations,
    ) -> None:
        tool_function = self._build_state_toggle_tool_function(connection, state)
        self._register_tool(
            name=tool_name,
            description=description,
            tool_function=tool_function,
            annotations=annotations.model_copy(
                update={"title": description.rstrip(".")}
            ),
        )

    def _register_state_toggle_tools(
        self,
        connection: Connection,
        annotations: ToolAnnotations,
    ) -> None:
        self._register_state_toggle_tool(
            connection=connection,
            state=1,
            tool_name=f"turn_on_{connection.name}",
            description=f"Turn on {connection.name}.",
            annotations=annotations,
        )
        self._register_state_toggle_tool(
            connection=connection,
            state=0,
            tool_name=f"turn_off_{connection.name}",
            description=f"Turn off {connection.name}.",
            annotations=annotations,
        )

    def _register_stream_toggle_tool(
        self,
        microcontroller: Microcontroller,
        connection: Connection,
        state: int,
        tool_name: str,
        description: str,
        annotations: ToolAnnotations,
        meta: dict[str, Any] | None = None,
    ) -> None:
        tool_function = self._build_stream_toggle_tool_function(
            microcontroller=microcontroller,
            connection=connection,
            state=state,
        )
        self._register_tool(
            name=tool_name,
            description=description,
            tool_function=tool_function,
            annotations=annotations.model_copy(
                update={"title": description.rstrip(".")}
            ),
            meta=meta,
        )

    def _register_stream_toggle_tools(
        self,
        microcontroller: Microcontroller,
        connection: Connection,
        annotations: ToolAnnotations,
        meta: dict[str, Any] | None = None,
    ) -> None:
        self._register_stream_toggle_tool(
            microcontroller=microcontroller,
            connection=connection,
            state=1,
            tool_name=f"turn_on_{connection.name}_stream",
            description=f"Turn on continuous streaming for {connection.name}.",
            annotations=annotations,
            meta=meta,
        )
        self._register_stream_toggle_tool(
            microcontroller=microcontroller,
            connection=connection,
            state=0,
            tool_name=f"turn_off_{connection.name}_stream",
            description=f"Turn off continuous streaming for {connection.name}.",
            annotations=annotations,
            meta=meta,
        )

    # Hardware, camera, and model tool registration.

    def _register_hardware_tools(self) -> None:
        for microcontroller in self.hardware_system.microcontrollers:
            for connection in microcontroller.connections:
                self._register_connection_tools(microcontroller, connection)

        self._register_camera_tools()
        self._register_inference_tools()

    @staticmethod
    def _command_is_state_toggle(command: CommandSpec) -> bool:
        if command.method.strip().upper() != "WRITE":
            return False

        state = command.params.get("state")
        return state is not None and state.min == 0 and state.max == 1

    @classmethod
    def _connection_supports_state_toggle(cls, connection: Connection) -> bool:
        for command in CommandCompiler.command_specs(connection):
            if cls._command_is_state_toggle(command):
                return True
        return False

    @classmethod
    def _connection_supports_stream_toggle(cls, connection: Connection) -> bool:
        return (
            connection.stream_enabled
            and cls._connection_supports_state_toggle(connection)
        )

    def _register_connection_tools(
        self,
        microcontroller: Microcontroller,
        connection: Connection,
    ) -> None:
        commands = CommandCompiler.command_specs(connection)
        supports_stream = self._connection_supports_stream_toggle(connection)
        for command in commands:
            annotations = CommandCompiler.command_annotations(connection, command)
            self._register_connection_action(
                microcontroller,
                connection,
                command,
            )
            if not (supports_stream and self._command_is_state_toggle(command)):
                self._register_connection_tool(connection, command, annotations)

        if not self._connection_supports_state_toggle(connection):
            return

        for command in commands:
            if self._command_is_state_toggle(command):
                toggle_command = command
                break
        else:
            raise RuntimeError("State toggle command is not registered")
        toggle_annotations = CommandCompiler.command_annotations(
            connection,
            toggle_command,
        )
        if supports_stream:
            self._register_stream_toggle_tools(
                microcontroller,
                connection,
                toggle_annotations,
                meta=stage_metadata(ToolStage.OBSERVATION),
            )
        else:
            self._register_state_toggle_tools(connection, toggle_annotations)

    def _register_camera_tools(self) -> None:
        for camera in self.hardware_system.cameras:
            camera_key = camera.camera_id

            def build_capture_frames_tool(camera_key: str):
                def capture_frames_from_camera(
                    image_count: Annotated[int, Field(ge=1, le=20)] = 1,
                    interval_seconds: Annotated[
                        float,
                        Field(ge=0.0, le=60.0),
                    ] = 0.0,
                ) -> list[str]:
                    frames = self.camera_runtime.capture_frames(
                        camera_key=camera_key,
                        image_count=image_count,
                        interval_seconds=interval_seconds,
                    )
                    encoded_frames: list[str] = []
                    for frame in frames:
                        encoded_frames.append(frame.to_base64_string())
                    return encoded_frames

                return capture_frames_from_camera

            self._register_tool(
                name=f"capture_frames_from_{camera.name}",
                description=(
                    f"Capture one or more current images from {camera.name}. "
                    "image_count controls the batch size and interval_seconds "
                    "controls the delay between images. Returns the images as "
                    "Base64 strings for precise vision inference."
                ),
                tool_function=build_capture_frames_tool(camera_key),
                annotations=ToolAnnotations(
                    title=f"Capture frames from {camera.name}",
                    readOnlyHint=True,
                    destructiveHint=False,
                    idempotentHint=True,
                    openWorldHint=False,
                ),
            )

    def _register_inference_tools(self) -> None:
        registered_models: dict[str, tuple[str, Inference]] = {}
        for model_id, inference in self.model_runtime.model_inferences.items():
            if inference.name in registered_models:
                raise ValueError(
                    f"Inference model name must be unique: {inference.name}"
                )
            registered_models[inference.name] = (model_id, inference)

        for model_id, model in registered_models.values():
            self._register_inference_model_tools(model_id, model)

        if registered_models:
            self._register_model_catalog_tool(registered_models)

    def _register_inference_model_tools(
        self,
        model_id: str,
        model: Inference,
    ) -> None:
        def turn_on_inference() -> None:
            self.model_runtime.turn_on_model(model_id)

        def turn_off_inference() -> None:
            self.model_runtime.turn_off_model(model_id)

        self._register_tool(
            name=f"turn_on_{model.name}",
            description=f"Start continuous inference for {model.name}.",
            tool_function=turn_on_inference,
            annotations=ToolAnnotations(
                title=f"Start continuous inference for {model.name}",
                readOnlyHint=False,
                destructiveHint=False,
                idempotentHint=True,
                openWorldHint=not isinstance(
                    model,
                    ObjectDetectionModelInference,
                ),
            ),
            meta=stage_metadata(ToolStage.OBSERVATION),
        )
        self._register_tool(
            name=f"turn_off_{model.name}",
            description=f"Stop continuous inference for {model.name}.",
            tool_function=turn_off_inference,
            annotations=ToolAnnotations(
                title=f"Stop continuous inference for {model.name}",
                readOnlyHint=False,
                destructiveHint=False,
                idempotentHint=True,
                openWorldHint=False,
            ),
            meta=stage_metadata(ToolStage.OBSERVATION),
        )

        if isinstance(model, ObjectDetectionModelInference):
            self._register_object_detection_tools(model_id, model)
        else:
            self._register_vision_language_model_tools(model_id, model)

    def _register_object_detection_tools(
        self,
        model_id: str,
        model: ObjectDetectionModelInference,
    ) -> None:
        def read_model_output(camera_id: str) -> dict[str, object]:
            result = self.model_runtime.read_model_output(model_id, camera_id)
            return result.model_dump(mode="json", exclude={"frame"})

        def predict_with_model(
            camera_ids: Annotated[list[str], Field(min_length=1)],
        ) -> list[dict[str, object]]:
            results = self.model_runtime.single_inference(model_id, camera_ids)
            serialized_results: list[dict[str, object]] = []
            for result in results:
                serialized_results.append(
                    result.model_dump(mode="json", exclude={"frame"})
                )
            return serialized_results

        self._register_tool(
            name=f"read_{model.name}",
            description=(
                f"Read the latest continuous inference output from "
                f"{model.name} for a subscribed camera ID."
            ),
            tool_function=read_model_output,
            annotations=ToolAnnotations(
                title=f"Read latest inference from {model.name}",
                readOnlyHint=True,
                destructiveHint=False,
                idempotentHint=True,
                openWorldHint=False,
            ),
        )
        self._register_tool(
            name=f"perform_single_{model.name}",
            description=(
                f"{model.description} Provide one or more IDs of subscribed "
                "cameras with current frames."
            ),
            tool_function=predict_with_model,
            annotations=ToolAnnotations(
                title=f"Perform one-shot inference with {model.name}",
                readOnlyHint=True,
                destructiveHint=False,
                idempotentHint=True,
                openWorldHint=False,
            ),
        )

    def _register_vision_language_model_tools(
        self,
        model_id: str,
        model: Inference,
    ) -> None:
        def read_model_output(
            camera_id: str,
        ) -> VisionLanguageModelFrameEnvironment:
            return self.model_runtime.read_model_output(model_id, camera_id)

        def predict_with_model(
            frames: Annotated[list[str], Field(min_length=1)],
        ) -> VisionLanguageModelFrameEnvironment:
            return self.model_runtime.single_inference(model_id, frames)

        self._register_tool(
            name=f"read_{model.name}",
            description=(
                f"Read the latest continuous inference output from "
                f"{model.name} for a subscribed camera ID."
            ),
            tool_function=read_model_output,
            annotations=ToolAnnotations(
                title=f"Read latest inference from {model.name}",
                readOnlyHint=True,
                destructiveHint=False,
                idempotentHint=True,
                openWorldHint=False,
            ),
        )
        self._register_tool(
            name=f"perform_single_{model.name}",
            description=(
                f"{model.description} Provide one or more Base64 image strings."
            ),
            tool_function=predict_with_model,
            annotations=ToolAnnotations(
                title=f"Perform one-shot inference with {model.name}",
                readOnlyHint=True,
                destructiveHint=False,
                idempotentHint=True,
                openWorldHint=True,
            ),
        )

    def _register_model_catalog_tool(
        self,
        registered_models: dict[str, tuple[str, Inference]],
    ) -> None:
        def list_configured_models() -> list[ModelCatalogEntry]:
            catalog: list[ModelCatalogEntry] = []
            for model_id, model in registered_models.values():
                model_type = (
                    "object_detection"
                    if isinstance(model, ObjectDetectionModelInference)
                    else "vision_language_model"
                )
                cameras: list[SubscribedCameraCatalogEntry] = []
                for camera in model.subscribed_cameras:
                    cameras.append(
                        SubscribedCameraCatalogEntry(
                            camera_id=camera.camera_id,
                            name=camera.name,
                        )
                    )
                catalog.append(
                    ModelCatalogEntry(
                        model_id=model_id,
                        name=model.name,
                        description=model.description,
                        model_type=model_type,
                        subscribed_cameras=cameras,
                        is_running=model.is_running,
                        turn_on_tool=f"turn_on_{model.name}",
                        turn_off_tool=f"turn_off_{model.name}",
                        read_tool=f"read_{model.name}",
                        single_inference_tool=f"perform_single_{model.name}",
                    )
                )
            return catalog

        self._register_tool(
            name="list_configured_models",
            description=(
                "List configured inference models, their model IDs, "
                "subscribed camera IDs, current running state, and exact "
                "lifecycle, read, and single-inference tool names."
            ),
            tool_function=list_configured_models,
            annotations=ToolAnnotations(
                title="List configured inference models",
                readOnlyHint=True,
                destructiveHint=False,
                idempotentHint=True,
                openWorldHint=False,
            ),
        )

    # Reaction and event catalog tools.

    def _register_reaction_tools(self) -> None:
        def insert_reaction(
            event_type: str,
            microcontroller_id: str,
            event_name: str,
            expected_value: Annotated[
                StrictFloat,
                Field(allow_inf_nan=False),
            ],
            operator: OperatorEnum,
            callback_body: str,
            trigger_mode: ReactionTriggerModeEnum = ReactionTriggerModeEnum.REPEAT,
        ) -> dict[str, str]:
            return self.agent_runtime.insert_reaction(
                event_type=event_type,
                microcontroller_id=microcontroller_id,
                event_name=event_name,
                expected_value=expected_value,
                operator=operator,
                callback_body=callback_body,
                trigger_mode=trigger_mode,
            )

        self._register_tool(
            name="insert_reaction",
            description=(
                "Create and register a reaction for a hardware event. "
                "callback_body must contain only the Python statements for "
                "async callback(mcp_url, value). The runtime imports httpx "
                "and fastmcp.Client, adds the fixed function definition, and "
                "binds the configured MCP URL and finite-float sensor value. "
                "The agent must use the mcp_url parameter and must not provide "
                "or hardcode an endpoint."
            ),
            tool_function=insert_reaction,
            annotations=ToolAnnotations(
                title="Create an event reaction",
                readOnlyHint=False,
                destructiveHint=False,
                idempotentHint=False,
                openWorldHint=False,
            ),
        )

        def delete_reaction(
            event_type: str,
            microcontroller_id: str,
            event_name: str,
        ) -> dict[str, str]:
            return self.agent_runtime.delete_reaction(
                event_type=event_type,
                microcontroller_id=microcontroller_id,
                event_name=event_name,
            )

        self._register_tool(
            name="delete_reaction",
            description=(
                "Delete the reaction registered for a hardware event and remove "
                "its local callback script."
            ),
            tool_function=delete_reaction,
            annotations=ToolAnnotations(
                title="Delete an event reaction",
                readOnlyHint=False,
                destructiveHint=True,
                idempotentHint=False,
                openWorldHint=False,
            ),
        )

    def _register_event_catalog_tool(self) -> None:
        def list_reaction_events() -> EventCatalog:
            return self.get_event_catalog()

        self._register_tool(
            name="list_reaction_events",
            description=(
                "List the registered hardware events that can be used "
                "when creating reactions."
            ),
            tool_function=list_reaction_events,
            annotations=ToolAnnotations(
                title="List events available for reactions",
                readOnlyHint=True,
                destructiveHint=False,
                idempotentHint=True,
                openWorldHint=False,
            ),
        )
