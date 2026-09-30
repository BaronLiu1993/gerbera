from dataclasses import dataclass, field
from inspect import Parameter, Signature
import logging
import time
from typing import Annotated, Any, Callable

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from gerbera_sdk.events.buffer import Buffer
from gerbera_sdk.firmware.firmware_schema import (
    CommandSpec,
    ParameterSpec,
)
from gerbera_sdk.events.event import Event
from gerbera_sdk.events.event_bus import EventBus, EventKey
from gerbera_sdk.events.event_listener import EventListener
from gerbera_sdk.events.event_worker import EventWorker
from gerbera_sdk.inference.model_types import (
    ModelCatalogEntry,
    ModelCatalogType,
    SubscribedCameraCatalogEntry,
)
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.hardware_plan import (
    HardwarePlan,
    ResolvedBoard,
    ResolvedConnection,
    StateKey,
)
from gerbera_sdk.models.runtime.board_runtime import BoardRuntime
from gerbera_sdk.models.runtime.camera_runtime import CameraRuntime
from gerbera_sdk.models.runtime.command_runtime import CommandCompiler
from gerbera_sdk.models.runtime.model_runtime import ModelRuntime
from gerbera_sdk.models.runtime.hardware_runtime import (
    ConnectionState,
    HardwareRuntime,
)
from gerbera_sdk.models.runtime.movement_runtime import MovementRuntime
from gerbera_sdk.events.reactions.reaction_bus import ReactionBus
from gerbera_sdk.events.reactions.reaction_executor import ReactionToolRegistry
from gerbera_sdk.events.reactions.reaction_schema import (
    CreateReactionSchema,
    DeleteReactionResultSchema,
    DeleteReactionSchema,
    ReactionEventSchema,
    ReactionSchema,
)
from gerbera_sdk.inference import (
    Inference,
    ObjectDetectionModelInference,
    VisionLanguageModelInference,
    VisionLanguageModelFrameEnvironment,
)

LOGGER = logging.getLogger(__name__)


@dataclass
class ServerRuntime:
    hardware_system: HardwareSystem
    hardware_plan: HardwarePlan
    board_runtime: BoardRuntime
    event_bus: EventBus
    event_worker: EventWorker
    app: FastMCP
    camera_runtime: CameraRuntime
    model_runtime: ModelRuntime
    event_listener: EventListener
    reaction_bus: ReactionBus
    hardware_runtime: HardwareRuntime
    movement_runtime: MovementRuntime | None = None
    reaction_tool_registry: ReactionToolRegistry = field(
        default_factory=ReactionToolRegistry
    )
    event_read_timeout_seconds: float = 1.0
    event_read_poll_seconds: float = 0.02

    def register_tools(self) -> None:
        self.register_hardware_tools()
        self.register_movement_tools()
        self.register_reaction_tools()
        self.register_reaction_catalog_tool()
        self.register_hardware_state_tool()
        self.register_environment_state_tool()

    @staticmethod
    def model_catalog_type(model: Inference) -> ModelCatalogType:
        if isinstance(model, ObjectDetectionModelInference):
            return "object_detection"
        if isinstance(model, VisionLanguageModelInference):
            return "vision_language_model"
        raise ValueError(f"Unsupported inference model type: {type(model).__name__}")

    def register_connection_event(
        self,
        board: ResolvedBoard,
        connection: ResolvedConnection,
        event_type: str,
    ) -> None:
        streamable = event_type == "STREAM"
        if streamable and not connection.stream_enabled:
            return

        event_key = (
            event_type,
            board.microcontroller_id,
            connection.event_name,
        )
        event = Event(
            event_type=event_type,
            microcontroller_id=board.microcontroller_id,
            event_name=connection.event_name,
            connection_name=connection.name,
            component_type=connection.component_type,
            streamable=streamable,
            table_name=connection.event_name,
            buffer=Buffer(
                table_name=connection.event_name,
                event_worker=self.event_worker,
            ),
            event_key=event_key,
            latest_val=None,
        )
        self.event_bus.write_event(
            event_type,
            board.microcontroller_id,
            connection.event_name,
            event,
        )

    def register_events(self) -> None:
        for board in self.hardware_plan.boards:
            for connection in board.connections:
                self.register_connection_event(
                    board,
                    connection,
                    "MCP",
                )
                self.register_connection_event(
                    board,
                    connection,
                    "STREAM",
                )

    def get_event_catalog(
        self,
    ) -> dict[str, dict[str, dict[str, dict[str, object]]]]:
        catalog: dict[str, dict[str, dict[str, dict[str, object]]]] = {}

        for event_key, event in self.event_bus.events.items():
            event_type, microcontroller_id, event_name = event_key
            connection = self.hardware_plan.connections_by_event_route[
                (microcontroller_id, event_name)
            ]
            metadata: dict[str, object] = {
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

    def send_read_command(
        self,
        event_key: EventKey,
    ) -> dict[str, object]:
        try:
            event = self.event_bus.get_event(*event_key)
            latest_value = event.read_latest()
        except Exception as exc:
            return {"success": False, "error": str(exc)}
        return {"success": True, "value": latest_value}

    def send_write_command(
        self,
        board: ResolvedBoard,
        connection: ResolvedConnection,
        action: str,
        params: dict[str, object],
    ) -> dict[str, object]:
        try:
            transport = self.board_runtime.get_transport(
                board.microcontroller_id
            )
            built_command = CommandCompiler.build_command(
                connection,
                action=action,
                params=params,
            )

            transport.write(built_command)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        return {"success": True}

    def register_connection_action(
        self,
        board: ResolvedBoard,
        connection: ResolvedConnection,
        command: CommandSpec,
    ) -> None:
        action = command.method.strip().upper()

        def action_function(
            params: dict[str, object],
        ) -> dict[str, object]:
            return self.send_write_command(
                board=board,
                connection=connection,
                action=action,
                params=params,
            )

        connection.register_action(action, action_function)

    def build_tool_function(
        self,
        connection: ResolvedConnection,
        command: CommandSpec,
    ) -> Callable[..., dict[str, object]]:
        action = command.method.strip().upper()
        if action == "READ":

            def read_tool_function() -> dict[str, object]:
                return self.send_read_command(
                    (
                        "MCP",
                        connection.microcontroller_id,
                        connection.event_name,
                    )
                )

            return read_tool_function

        if not command.params:

            def tool_function() -> dict[str, object]:
                return connection.perform_action(action, {})

            return tool_function

        def tool_function(**values: Any) -> dict[str, object]:
            params = {
                name: value for name, value in values.items() if value is not None
            }
            return connection.perform_action(action, params)

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
                ge=parameter.min,
                le=parameter.max,
            ),
        ]

    def build_toggle_tool_function(
        self,
        connection: ResolvedConnection,
        state: int,
        state_key: StateKey | None = None,
        stream_board: ResolvedBoard | None = None,
    ) -> Callable[[], dict[str, object]]:
        def tool_function() -> dict[str, object]:
            response = connection.perform_action("WRITE", {"state": state})

            if stream_board is not None and state == 0:
                stream_event = self.event_bus.get_event(
                    "STREAM",
                    stream_board.microcontroller_id,
                    connection.event_name,
                )
                stream_event.flush()
                self.event_worker.wait_until_idle()

            if response["success"] and state_key is not None:
                self.hardware_runtime.update_state(
                    state_key,
                    ConnectionState(value=str(state), unit=None),
                )
            return response

        return tool_function

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
        self.register_tool(
            name=tool_name,
            description=description,
            tool_function=tool_function,
            annotations=annotations,
            meta={
                "key": self.hardware_runtime.state_key_label(state_key),
            },
        )

    def register_tool(
        self,
        name: str,
        description: str,
        tool_function: Callable[..., Any],
        annotations: ToolAnnotations,
        meta: dict[str, Any] | None = None,
    ) -> None:
        self.reaction_tool_registry.register(
            name,
            tool_function,
            annotations,
        )
        self.app.tool(
            name=name,
            description=description,
            annotations=annotations,
            meta=meta,
        )(tool_function)

    def validate_reaction_event(self, event: ReactionEventSchema) -> None:
        try:
            self.event_bus.get_event(*event.event_key)
        except RuntimeError as exc:
            raise ValueError(
                f"Unknown reaction event: {event.event_key}"
            ) from exc

        route = (event.microcontroller_id, event.event_name)
        connection = self.hardware_plan.connections_by_event_route[route]
        payload_fields = {
            state_key[2]
            for state_key in CommandCompiler.state_keys(connection)
        }
        if event.payload_field not in payload_fields:
            raise ValueError(
                "Unknown reaction payload field: "
                f"{event.payload_field} for {event.event_name}"
            )

    def validate_reaction_definition(
        self,
        definition: CreateReactionSchema,
    ) -> None:
        self.validate_reaction_event(definition.event)
        self.reaction_tool_registry.validate_action(definition.action)

    def restore_reactions(self) -> None:
        for definition in self.reaction_bus.store.load():
            try:
                self.validate_reaction_definition(definition)
                self.reaction_bus.register_definition(
                    definition,
                    persist=False,
                )
            except ValueError as exc:
                LOGGER.warning(
                    "Ignoring unusable stored reaction %s: %s",
                    definition.reaction_id,
                    exc,
                )

    def register_reaction_tools(self) -> None:
        self.reaction_bus.configure_executor(self.reaction_tool_registry)
        self.restore_reactions()

        def create_reaction(
            reaction: CreateReactionSchema,
        ) -> ReactionSchema:
            self.validate_reaction_definition(reaction)
            return self.reaction_bus.create_reaction(reaction)

        def list_reactions() -> list[ReactionSchema]:
            return self.reaction_bus.list_reactions()

        def delete_reaction(
            request: DeleteReactionSchema,
        ) -> DeleteReactionResultSchema:
            deleted = self.reaction_bus.delete_reaction(
                request.reaction_id
            )
            return DeleteReactionResultSchema(deleted=deleted)

        self.register_tool(
            name="create_reaction",
            description=(
                "Create a persisted reaction that invokes a Gerbera tool "
                "when a hardware event condition matches."
            ),
            tool_function=create_reaction,
            annotations=ToolAnnotations(
                title="Create reaction",
                readOnlyHint=False,
                openWorldHint=False,
            ),
        )
        self.register_tool(
            name="list_reactions",
            description="List active reactions and their runtime status.",
            tool_function=list_reactions,
            annotations=ToolAnnotations(
                title="List reactions",
                readOnlyHint=True,
                openWorldHint=False,
            ),
        )
        self.register_tool(
            name="delete_reaction",
            description="Permanently delete an active reaction.",
            tool_function=delete_reaction,
            annotations=ToolAnnotations(
                title="Delete reaction",
                readOnlyHint=False,
                destructiveHint=True,
                openWorldHint=False,
            ),
        )

    def register_state_toggle_tool(
        self,
        connection: ResolvedConnection,
        state: int,
        tool_name: str,
        description: str,
        annotations: ToolAnnotations,
    ) -> None:
        state_key = CommandCompiler.state_keys(connection)[0]
        tool_function = self.build_toggle_tool_function(
            connection=connection,
            state=state,
            state_key=state_key,
        )
        self.register_tool(
            name=tool_name,
            description=description,
            tool_function=tool_function,
            annotations=annotations.model_copy(
                update={"title": description.rstrip(".")}
            ),
            meta={
                "key": self.hardware_runtime.state_key_label(state_key),
            },
        )

    def register_state_toggle_tools(
        self,
        connection: ResolvedConnection,
        annotations: ToolAnnotations,
    ) -> None:
        self.register_state_toggle_tool(
            connection=connection,
            state=1,
            tool_name=f"turn_on_{connection.name}",
            description=f"Turn on {connection.name}.",
            annotations=annotations,
        )
        self.register_state_toggle_tool(
            connection=connection,
            state=0,
            tool_name=f"turn_off_{connection.name}",
            description=f"Turn off {connection.name}.",
            annotations=annotations,
        )

    def register_stream_toggle_tool(
        self,
        board: ResolvedBoard,
        connection: ResolvedConnection,
        state: int,
        tool_name: str,
        description: str,
        annotations: ToolAnnotations,
        meta: dict[str, Any] | None = None,
    ) -> None:
        state_key = CommandCompiler.state_key(
            connection,
            "stream_enabled",
        )
        tool_function = self.build_toggle_tool_function(
            connection=connection,
            state=state,
            state_key=state_key,
            stream_board=board,
        )
        self.register_tool(
            name=tool_name,
            description=description,
            tool_function=tool_function,
            annotations=annotations.model_copy(
                update={"title": description.rstrip(".")}
            ),
            meta=meta
            or {
                "key": self.hardware_runtime.state_key_label(state_key),
            },
        )

    def register_stream_toggle_tools(
        self,
        board: ResolvedBoard,
        connection: ResolvedConnection,
        annotations: ToolAnnotations,
        meta: dict[str, Any] | None = None,
    ) -> None:
        self.register_stream_toggle_tool(
            board=board,
            connection=connection,
            state=1,
            tool_name=f"turn_on_{connection.name}_stream",
            description=f"Turn on continuous streaming for {connection.name}.",
            annotations=annotations,
            meta=meta,
        )
        self.register_stream_toggle_tool(
            board=board,
            connection=connection,
            state=0,
            tool_name=f"turn_off_{connection.name}_stream",
            description=f"Turn off continuous streaming for {connection.name}.",
            annotations=annotations,
            meta=meta,
        )

    def register_hardware_tools(self) -> None:
        for board in self.hardware_plan.boards:
            for connection in board.connections:
                self.register_connection_tools(board, connection)

        self.register_camera_tools()
        self.register_inference_tools()

    @staticmethod
    def command_is_state_toggle(command: CommandSpec) -> bool:
        if command.method.strip().upper() != "WRITE":
            return False

        state = command.params.get("state")
        return state is not None and state.min == 0 and state.max == 1

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
        board: ResolvedBoard,
        connection: ResolvedConnection,
    ) -> None:
        commands = CommandCompiler.command_specs(connection)
        supports_stream = self.connection_supports_stream_toggle(connection)
        for command in commands:
            annotations = CommandCompiler.command_annotations(connection, command)
            self.register_connection_action(
                board,
                connection,
                command,
            )
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
        toggle_annotations = CommandCompiler.command_annotations(
            connection,
            toggle_command,
        )
        if supports_stream:
            self.register_stream_toggle_tools(
                board,
                connection,
                toggle_annotations,
            )
        else:
            self.register_state_toggle_tools(connection, toggle_annotations)

    def register_camera_tools(self) -> None:
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

            self.register_tool(
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
                    openWorldHint=False,
                ),
            )

    def register_inference_tools(self) -> None:
        self.model_runtime.register_models()
        registered_models: dict[str, tuple[str, Inference]] = {}
        for model_id, registered_model in (
            self.model_runtime.registered_models.items()
        ):
            inference = registered_model.inference
            if inference.name in registered_models:
                raise ValueError(
                    f"Inference model name must be unique: {inference.name}"
                )
            registered_models[inference.name] = (model_id, inference)

        for model_id, model in registered_models.values():
            self.register_inference_model_tools(model_id, model)

        if registered_models:
            self.register_model_catalog_tool(registered_models)

    def register_inference_model_tools(
        self,
        model_id: str,
        model: Inference,
    ) -> None:
        if isinstance(model, VisionLanguageModelInference):

            def turn_on_inference(
                prompt: Annotated[str, Field(min_length=1)],
            ) -> None:
                self.model_runtime.turn_on_model_stream(
                    model_id=model_id,
                    prompt=prompt,
                )
        else:
            def turn_on_inference() -> None:
                self.model_runtime.turn_on_model_stream(
                    model_id=model_id,
                )

        def turn_off_inference() -> None:
            self.model_runtime.turn_off_model_stream(
                model_id=model_id,
            )

        self.register_tool(
            name=f"turn_on_{model.name}",
            description=f"Start continuous inference for {model.name}.",
            tool_function=turn_on_inference,
            annotations=ToolAnnotations(
                title=f"Start continuous inference for {model.name}",
                readOnlyHint=False,
                openWorldHint=not isinstance(
                    model,
                    ObjectDetectionModelInference,
                ),
            ),
        )
        self.register_tool(
            name=f"turn_off_{model.name}",
            description=f"Stop continuous inference for {model.name}.",
            tool_function=turn_off_inference,
            annotations=ToolAnnotations(
                title=f"Stop continuous inference for {model.name}",
                readOnlyHint=False,
                openWorldHint=False,
            ),
        )

        if isinstance(model, ObjectDetectionModelInference):
            self.register_object_detection_tools(model_id, model)
        else:
            self.register_vision_language_model_tools(model_id, model)

    def register_movement_tools(self) -> None:
        if self.movement_runtime is None:
            return

        def list_movement_systems() -> list[str]:
            return self.movement_runtime.list_movement_systems()

        def get_current_movement_state() -> dict[str, object]:
            return self.movement_runtime.get_movement_context()

        def solve_forward_kinematics(
            movement_system_name: str,
            target_link_name: str,
        ) -> dict[str, object]:
            return self.movement_runtime.solve_forward_kinematics(
                movement_system_name=movement_system_name,
                target_link_name=target_link_name,
            )

        def solve_inverse_kinematics(
            movement_system_name: str,
            target_link_name: str,
            target_position_m: Annotated[
                list[float],
                Field(min_length=3, max_length=3),
            ],
            target_orientation_rpy_rad: Annotated[
                list[float],
                Field(min_length=3, max_length=3),
            ],
        ) -> dict[str, float]:
            return self.movement_runtime.solve_inverse_kinematics(
                movement_system_name=movement_system_name,
                target_link_name=target_link_name,
                target_position_m=(
                    target_position_m[0],
                    target_position_m[1],
                    target_position_m[2],
                ),
                target_orientation_rpy_rad=(
                    target_orientation_rpy_rad[0],
                    target_orientation_rpy_rad[1],
                    target_orientation_rpy_rad[2],
                ),
            )

        self.register_tool(
            name="list_movement_systems",
            description="List registered movement system names.",
            tool_function=list_movement_systems,
            annotations=ToolAnnotations(
                title="List movement systems",
                readOnlyHint=True,
                openWorldHint=False,
            ),
        )
        self.register_tool(
            name="get_current_movement_state",
            description=(
                "Read current movement system state, joint definitions, links, "
                "target links, motor connections, limits, and joint positions."
            ),
            tool_function=get_current_movement_state,
            annotations=ToolAnnotations(
                title="Get current movement state",
                readOnlyHint=True,
                openWorldHint=False,
            ),
        )
        self.register_tool(
            name="solve_forward_kinematics",
            description=(
                "Compute the current pose of a target link in a registered "
                "movement system from the runtime joint positions."
            ),
            tool_function=solve_forward_kinematics,
            annotations=ToolAnnotations(
                title="Solve forward kinematics",
                readOnlyHint=True,
                openWorldHint=False,
            ),
        )
        self.register_tool(
            name="solve_inverse_kinematics",
            description=(
                "Compute joint positions for a target link to reach a target "
                "position and roll-pitch-yaw orientation."
            ),
            tool_function=solve_inverse_kinematics,
            annotations=ToolAnnotations(
                title="Solve inverse kinematics",
                readOnlyHint=True,
                openWorldHint=False,
            ),
        )

    def register_object_detection_tools(
        self,
        model_id: str,
        model: ObjectDetectionModelInference,
    ) -> None:
        def read_model_output() -> dict[str, object]:
            result = self.model_runtime.read_model_output(
                model_id,
                "object_detection",
            )
            return result.model_dump(mode="json", exclude={"frame"})

        def predict_with_model() -> dict[str, object]:
            result = self.model_runtime.perform_object_detection(model_id)
            return result.model_dump(mode="json", exclude={"frame"})

        self.register_tool(
            name=f"read_{model.name}",
            description=(
                f"Read the latest continuous inference output from "
                f"{model.name} for its subscribed camera."
            ),
            tool_function=read_model_output,
            annotations=ToolAnnotations(
                title=f"Read latest inference from {model.name}",
                readOnlyHint=True,
                openWorldHint=False,
            ),
        )
        self.register_tool(
            name=f"perform_single_{model.name}",
            description=(
                f"{model.description} Uses the current frame from the model's "
                "subscribed camera."
            ),
            tool_function=predict_with_model,
            annotations=ToolAnnotations(
                title=f"Perform one-shot inference with {model.name}",
                readOnlyHint=True,
                openWorldHint=False,
            ),
        )

    def register_vision_language_model_tools(
        self,
        model_id: str,
        model: VisionLanguageModelInference,
    ) -> None:
        def read_scene_objects() -> VisionLanguageModelFrameEnvironment:
            return self.model_runtime.read_model_output(
                model_id,
                "locate_object",
            )

        def read_scene_analysis() -> str:
            return self.model_runtime.read_model_output(
                model_id,
                "scene_analysis",
            )

        def capture_scene_objects(
            prompt: Annotated[str, Field(min_length=1)],
            frames: Annotated[list[str], Field(min_length=1)],
        ) -> VisionLanguageModelFrameEnvironment:
            return self.model_runtime.locate_objects(
                model_id=model_id,
                frames=frames,
                prompt=prompt,
            )

        def analyse_scene(
            prompt: Annotated[str, Field(min_length=1)],
            frames: Annotated[list[str], Field(min_length=1)],
        ) -> str:
            return self.model_runtime.analyze_scene(
                model_id=model_id,
                frames=frames,
                prompt=prompt,
            )

        self.register_tool(
            name=f"read_scene_objects_{model.name}",
            description=(
                f"Read the latest scene-object output from "
                f"{model.name} for its subscribed camera."
            ),
            tool_function=read_scene_objects,
            annotations=ToolAnnotations(
                title=f"Read latest scene objects from {model.name}",
                readOnlyHint=True,
                openWorldHint=False,
            ),
        )
        self.register_tool(
            name=f"read_scene_analysis_{model.name}",
            description=(
                f"Read the latest scene-analysis output from "
                f"{model.name} for its subscribed camera."
            ),
            tool_function=read_scene_analysis,
            annotations=ToolAnnotations(
                title=f"Read latest scene analysis from {model.name}",
                readOnlyHint=True,
                openWorldHint=False,
            ),
        )
        self.register_tool(
            name=f"capture_scene_objects_{model.name}",
            description=(
                f"{model.description} Provide a prompt and one or more "
                "Base64 image strings. Returns structured objects, pixel "
                "locations, and depth estimates."
            ),
            tool_function=capture_scene_objects,
            annotations=ToolAnnotations(
                title=f"Capture scene objects with {model.name}",
                readOnlyHint=True,
                openWorldHint=True,
            ),
        )
        self.register_tool(
            name=f"analyse_scene_{model.name}",
            description=(
                f"{model.description} Provide a prompt and one or more "
                "Base64 image strings. Returns plain text scene analysis."
            ),
            tool_function=analyse_scene,
            annotations=ToolAnnotations(
                title=f"Analyse scene with {model.name}",
                readOnlyHint=True,
                openWorldHint=True,
            ),
        )

    def register_model_catalog_tool(
        self,
        registered_models: dict[str, tuple[str, Inference]],
    ) -> None:
        def list_configured_models() -> list[ModelCatalogEntry]:
            with self.model_runtime.lock:
                running_model_ids = {
                    model_id
                    for model_id, stream in self.model_runtime.model_streams.items()
                    if stream.thread.is_alive()
                }
            catalog: list[ModelCatalogEntry] = []
            for model_id, model in registered_models.values():
                camera = model.subscribed_camera
                catalog.append(
                    ModelCatalogEntry(
                        model_id=model_id,
                        name=model.name,
                        description=model.description,
                        model_type=self.model_catalog_type(model),
                        subscribed_camera=SubscribedCameraCatalogEntry(
                            camera_id=camera.camera_id,
                            name=camera.name,
                        ),
                        is_running=model_id in running_model_ids,
                        turn_on_tool=f"turn_on_{model.name}",
                        turn_off_tool=f"turn_off_{model.name}",
                        read_tool=(
                            f"read_scene_objects_{model.name}"
                            if isinstance(model, VisionLanguageModelInference)
                            else f"read_{model.name}"
                        ),
                        single_inference_tool=(
                            f"capture_scene_objects_{model.name}"
                            if isinstance(model, VisionLanguageModelInference)
                            else f"perform_single_{model.name}"
                        ),
                        scene_objects_read_tool=(
                            f"read_scene_objects_{model.name}"
                            if isinstance(model, VisionLanguageModelInference)
                            else None
                        ),
                        scene_objects_tool=(
                            f"capture_scene_objects_{model.name}"
                            if isinstance(model, VisionLanguageModelInference)
                            else None
                        ),
                        scene_analysis_read_tool=(
                            f"read_scene_analysis_{model.name}"
                            if isinstance(model, VisionLanguageModelInference)
                            else None
                        ),
                        scene_analysis_tool=(
                            f"analyse_scene_{model.name}"
                            if isinstance(model, VisionLanguageModelInference)
                            else None
                        ),
                    )
                )
            return catalog

        self.register_tool(
            name="list_configured_models",
            description=(
                "List configured inference models, their model IDs, "
                "subscribed camera, current running state, and exact "
                "lifecycle, read, and single-inference tool names."
            ),
            tool_function=list_configured_models,
            annotations=ToolAnnotations(
                title="List configured inference models",
                readOnlyHint=True,
                openWorldHint=False,
            ),
        )

    def register_reaction_catalog_tool(self) -> None:
        def list_reaction_events() -> (
            dict[str, dict[str, dict[str, dict[str, object]]]]
        ):
            return self.get_event_catalog()

        self.register_tool(
            name="list_reaction_events",
            description=(
                "List the registered hardware events that can be used "
                "when creating reactions."
            ),
            tool_function=list_reaction_events,
            annotations=ToolAnnotations(
                title="List events available for reactions",
                readOnlyHint=True,
                openWorldHint=False,
            ),
        )

    def register_hardware_state_tool(self) -> None:
        self.register_tool(
            name="get_current_hardware_state",
            description=("Read the current hardware state memory."),
            tool_function=self.hardware_runtime.get_state_store,
            annotations=ToolAnnotations(
                title="Get current hardware state",
            ),
        )

    def register_environment_state_tool(self) -> None:
        self.register_tool(
            name="get_current_environment_state",
            description=("Read the current environment state from model outputs."),
            tool_function=self.model_runtime.get_model_state,
            annotations=ToolAnnotations(
                title="Get current environment state",
            ),
        )
