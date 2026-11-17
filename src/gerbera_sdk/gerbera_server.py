from dataclasses import dataclass
from inspect import Parameter, Signature
from typing import Annotated, Any, Callable

from fastmcp import FastMCP
from gerbera_protocol import RuntimeManifest
from gerbera_sdk.models.hardware.hardware_plan import HardwarePlan, ResolvedConnection
from gerbera_sdk.models.runtime.commands.command_executor import CommandExecutor
from gerbera_sdk.models.runtime.commands.command_runtime import CommandCompiler
from gerbera_sdk.models.runtime.commands.connection_control import ConnectionControl
from gerbera_sdk.models.runtime.perception.camera_runtime import CameraRuntime
from gerbera_sdk.models.runtime.perception.model_runtime import ModelRuntime
from mcp.types import ToolAnnotations
from pydantic import AfterValidator, Field

from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.reactions.reaction_bus import ReactionBus
from gerbera_sdk.events.reactions.reaction_executor import ReactionActionRegistry
from gerbera_sdk.events.reactions.reaction_schema import (
    CreateReactionSchema,
    DeleteReactionResultSchema,
    DeleteReactionSchema,
    ReactionSchema,
)
from gerbera_sdk.firmware.devices.config_schema import CommandConfig, ParameterConfig
from gerbera_sdk.firmware.devices.library import get_device_builder
from gerbera_sdk.firmware.parameter_schema import NumericChoice
from gerbera_sdk.inference import VisionLanguageModelFrameEnvironment
from gerbera_sdk.inference.model_descriptor import ModelDescriptor
from gerbera_sdk.inference.model_types import (
    ModelCatalogEntry,
    ModelCatalogType,
    SubscribedCameraCatalogEntry,
)
from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.runtime.state.hardware_runtime import HardwareRuntime

MODEL_CATALOG_TYPES = {
    "object_depth": "object_depth",
    "object_detection": "object_detection",
    "object_segmentation": "object_segmentation",
    "vision_language_model": "vision_language_model",
}

FRAME_MODEL_OUTPUT_NAMES = {
    "object_depth": "object_depth",
    "object_segmentation": "object_segmentation",
}

import json


@dataclass
class GerberaServer:
    hardware_plan: HardwarePlan
    hardware_runtime: HardwareRuntime
    controls: ConnectionControl
    commands: CommandExecutor
    hardware_system: HardwareSystem
    camera_runtime: CameraRuntime
    model_runtime: ModelRuntime
    reactions: ReactionBus
    event_bus: EventBus
    app: FastMCP
    actions: ReactionActionRegistry

    def register(self) -> None:
        self.register_remote_resources()
        self.register_hardware_tools()
        self.register_camera_tools()
        self.register_inference_tools()
        # self.register_reaction_tools()
        # self.register_reaction_catalog_tool()
        self.register_hardware_state_tool()
        self.register_environment_state_tool()

    def register_tool(
        self,
        *,
        name: str,
        description: str,
        tool_function: Callable[..., Any],
        annotations: ToolAnnotations,
        meta: dict[str, Any] | None = None,
    ) -> None:
        reaction_tool_names = {
            "create_reaction",
            "delete_reaction",
            "list_reactions",
        }
        if annotations.readOnlyHint is False:
            if name not in reaction_tool_names:
                self.actions.register(name, tool_function)
        self.app.tool(
            name=name,
            description=description,
            annotations=annotations,
            meta=meta,
        )(tool_function)

    def build_tool_function(
        self,
        connection: ResolvedConnection,
        command: CommandConfig,
    ) -> Callable[..., dict[str, object]]:
        action = command.method.strip().upper()
        if not command.params:

            def tool_function() -> dict[str, object]:
                return self.commands.execute(connection, action, {})

            return tool_function

        def tool_function(**values: Any) -> dict[str, object]:
            params = {}
            for name, value in values.items():
                if value is not None:
                    params[name] = value
            return self.commands.execute(connection, action, params)

        parameters: list[Parameter] = []
        annotations: dict[str, Any] = {"return": dict[str, object]}
        for name, parameter in command.params.items():
            annotation = self.build_parameter_annotation(parameter)
            if parameter.required:
                default = Parameter.empty
            else:
                default = None
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
        parameter: ParameterConfig,
    ) -> Any:
        return Annotated[
            float,
            Field(
                description=parameter.description or None,
                strict=True,
                allow_inf_nan=False,
                json_schema_extra=parameter.domain.json_constraints(),
            ),
            AfterValidator(parameter.domain.validate_value),
        ]

    def register_connection_tool(
        self,
        connection: ResolvedConnection,
        command: CommandConfig,
        annotations: ToolAnnotations,
    ) -> None:
        description = command.description.strip()
        if not description:
            raise ValueError(
                f"Command description is required: {command.method},{connection.name}"
            )
        if connection.stream_enabled:
            description += (
                f" Collected data is stored in table `{connection.event_name}`."
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
            meta={"key": self.hardware_runtime.state_key_label(state_key)},
        )

    def state_toggle(
        self, connection: ResolvedConnection, state: int
    ) -> Callable[[], dict[str, object]]:
        def tool_function() -> dict[str, object]:
            return self.controls.set_state(connection, state)

        return tool_function

    def stream_toggle(
        self, connection: ResolvedConnection, state: int
    ) -> Callable[[], dict[str, object]]:
        def tool_function() -> dict[str, object]:
            return self.controls.set_stream_state(connection, state)

        return tool_function

    def register_state_toggle_tools(
        self,
        connection: ResolvedConnection,
        annotations: ToolAnnotations,
    ) -> None:
        state_key = CommandCompiler.state_keys(connection)[0]
        for state, verb in ((1, "on"), (0, "off")):
            description = f"Turn {verb} {connection.name}."
            self.register_tool(
                name=f"turn_{verb}_{connection.name}",
                description=description,
                tool_function=self.state_toggle(connection, state),
                annotations=annotations.model_copy(
                    update={"title": description.rstrip(".")}
                ),
                meta={"key": self.hardware_runtime.state_key_label(state_key)},
            )

    def register_stream_toggle_tools(
        self,
        connection: ResolvedConnection,
        annotations: ToolAnnotations,
    ) -> None:
        state_key = CommandCompiler.state_key(connection, "stream_enabled")
        for state, verb in ((1, "on"), (0, "off")):
            description = f"Turn {verb} continuous streaming for {connection.name}."
            self.register_tool(
                name=f"turn_{verb}_{connection.name}_stream",
                description=description,
                tool_function=self.stream_toggle(connection, state),
                annotations=annotations.model_copy(
                    update={"title": description.rstrip(".")}
                ),
                meta={"key": self.hardware_runtime.state_key_label(state_key)},
            )

    def register_hardware_tools(self) -> None:
        for board in self.hardware_plan.boards:
            for connection in board.connections:
                self.register_connection_tools(connection)

    @staticmethod
    def command_is_state_toggle(command: CommandConfig) -> bool:
        if command.method.strip().upper() != "WRITE":
            return False

        state = command.params.get("state")
        return (
            state is not None
            and isinstance(state.domain, NumericChoice)
            and set(state.domain.values) == {0.0, 1.0}
        )

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
        connection: ResolvedConnection,
    ) -> None:
        commands = CommandCompiler.command_specs(connection)
        supports_stream = self.connection_supports_stream_toggle(connection)
        for command in commands:
            annotations = self.command_annotations(connection, command)
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
        toggle_annotations = self.command_annotations(connection, toggle_command)
        if supports_stream:
            self.register_stream_toggle_tools(connection, toggle_annotations)
        else:
            self.register_state_toggle_tools(connection, toggle_annotations)

    @staticmethod
    def model_catalog_type(model: ModelDescriptor) -> ModelCatalogType:
        try:
            return MODEL_CATALOG_TYPES[model.model_type]
        except KeyError as error:
            raise ValueError(
                f"Unsupported inference model type: {type(model).__name__}"
            ) from error

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
                description=f"Capture one or more current images from {camera.name}. image_count controls the batch size and interval_seconds controls the delay between images. Returns the images as Base64 strings for precise vision inference.",
                tool_function=build_capture_frames_tool(camera_key),
                annotations=ToolAnnotations(
                    title=f"Capture frames from {camera.name}",
                    readOnlyHint=True,
                    openWorldHint=False,
                ),
            )

    def register_inference_tools(self) -> None:
        registered_models: dict[str, tuple[str, ModelDescriptor]] = {}
        for declaration in self.hardware_system.models:
            inference = ModelDescriptor.from_declaration(declaration)
            model_id = inference.model_id
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
        model: ModelDescriptor,
    ) -> None:
        if model.model_type == "vision_language_model":

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
                openWorldHint=model.model_type == "vision_language_model",
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

        tool_registrars: dict[str, Callable[[str, Any], None]] = {
            "object_depth": self.register_frame_model_tools,
            "object_detection": self.register_object_detection_tools,
            "object_segmentation": self.register_frame_model_tools,
            "vision_language_model": self.register_vision_language_model_tools,
        }
        try:
            registrar = tool_registrars[model.model_type]
        except KeyError as error:
            raise ValueError(
                f"Unsupported inference model type: {type(model).__name__}"
            ) from error
        registrar(model_id, model)

    def register_object_detection_tools(
        self,
        model_id: str,
        model: ModelDescriptor,
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
            description=f"Read the latest continuous inference output from {model.name} for its subscribed camera.",
            tool_function=read_model_output,
            annotations=ToolAnnotations(
                title=f"Read latest inference from {model.name}",
                readOnlyHint=True,
                openWorldHint=False,
            ),
        )
        self.register_tool(
            name=f"perform_single_{model.name}",
            description=f"{model.description} Uses the current frame from the model's subscribed camera.",
            tool_function=predict_with_model,
            annotations=ToolAnnotations(
                title=f"Perform one-shot inference with {model.name}",
                readOnlyHint=True,
                openWorldHint=False,
            ),
        )

    def register_frame_model_tools(
        self,
        model_id: str,
        model: ModelDescriptor,
    ) -> None:
        output_name = FRAME_MODEL_OUTPUT_NAMES[model.model_type]

        def read_model_output() -> dict[str, object]:
            result = self.model_runtime.read_model_output(
                model_id,
                output_name,
            )
            return result.model_dump(mode="json", exclude={"frame"})

        def predict_with_model() -> dict[str, object]:
            result = self.model_runtime.perform_frame_inference(model_id)
            return result.model_dump(mode="json", exclude={"frame"})

        self.register_tool(
            name=f"read_{model.name}",
            description=f"Read the latest continuous inference output from {model.name} for its subscribed camera.",
            tool_function=read_model_output,
            annotations=ToolAnnotations(
                title=f"Read latest inference from {model.name}",
                readOnlyHint=True,
                openWorldHint=False,
            ),
        )
        self.register_tool(
            name=f"perform_single_{model.name}",
            description=f"{model.description} Uses the current frame from the model's subscribed camera.",
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
        model: ModelDescriptor,
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
            description=f"Read the latest scene-object output from {model.name} for its subscribed camera.",
            tool_function=read_scene_objects,
            annotations=ToolAnnotations(
                title=f"Read latest scene objects from {model.name}",
                readOnlyHint=True,
                openWorldHint=False,
            ),
        )
        self.register_tool(
            name=f"read_scene_analysis_{model.name}",
            description=f"Read the latest scene-analysis output from {model.name} for its subscribed camera.",
            tool_function=read_scene_analysis,
            annotations=ToolAnnotations(
                title=f"Read latest scene analysis from {model.name}",
                readOnlyHint=True,
                openWorldHint=False,
            ),
        )
        self.register_tool(
            name=f"capture_scene_objects_{model.name}",
            description=f"{model.description} Provide a prompt and one or more Base64 image strings. Returns structured objects, pixel locations, and depth estimates.",
            tool_function=capture_scene_objects,
            annotations=ToolAnnotations(
                title=f"Capture scene objects with {model.name}",
                readOnlyHint=True,
                openWorldHint=True,
            ),
        )
        self.register_tool(
            name=f"analyse_scene_{model.name}",
            description=f"{model.description} Provide a prompt and one or more Base64 image strings. Returns plain text scene analysis.",
            tool_function=analyse_scene,
            annotations=ToolAnnotations(
                title=f"Analyse scene with {model.name}",
                readOnlyHint=True,
                openWorldHint=True,
            ),
        )

    def register_model_catalog_tool(
        self,
        registered_models: dict[str, tuple[str, ModelDescriptor]],
    ) -> None:
        def list_configured_models() -> list[ModelCatalogEntry]:
            with self.model_runtime.lock:
                running_model_ids = set()
                for model_id, stream in self.model_runtime.model_streams.items():
                    if stream.thread.is_alive():
                        running_model_ids.add(model_id)
            catalog: list[ModelCatalogEntry] = []
            for model_id, model in registered_models.values():
                camera = model.subscribed_camera
                read_tool = f"read_{model.name}"
                single_inference_tool = f"perform_single_{model.name}"
                scene_objects_read_tool = None
                scene_objects_tool = None
                scene_analysis_read_tool = None
                scene_analysis_tool = None

                if model.model_type == "vision_language_model":
                    scene_objects_read_tool = f"read_scene_objects_{model.name}"
                    scene_objects_tool = f"capture_scene_objects_{model.name}"
                    scene_analysis_read_tool = f"read_scene_analysis_{model.name}"
                    scene_analysis_tool = f"analyse_scene_{model.name}"
                    read_tool = scene_objects_read_tool
                    single_inference_tool = scene_objects_tool

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
                        read_tool=read_tool,
                        single_inference_tool=single_inference_tool,
                        scene_objects_read_tool=scene_objects_read_tool,
                        scene_objects_tool=scene_objects_tool,
                        scene_analysis_read_tool=scene_analysis_read_tool,
                        scene_analysis_tool=scene_analysis_tool,
                    )
                )
            return catalog

        self.register_tool(
            name="list_configured_models",
            description="List configured inference models, their model IDs, subscribed camera, current running state, and exact lifecycle, read, and single-inference tool names.",
            tool_function=list_configured_models,
            annotations=ToolAnnotations(
                title="List configured inference models",
                readOnlyHint=True,
                openWorldHint=False,
            ),
        )

    def register_reaction_tools(self) -> None:
        def create_reaction(
            reaction: CreateReactionSchema,
        ) -> ReactionSchema:
            return self.reactions.create_reaction(reaction)

        def list_reactions() -> list[ReactionSchema]:
            return self.reactions.list_reactions()

        def delete_reaction(
            request: DeleteReactionSchema,
        ) -> DeleteReactionResultSchema:
            deleted = self.reactions.delete_reaction(request.reaction_id)
            return DeleteReactionResultSchema(deleted=deleted)

        self.register_tool(
            name="create_reaction",
            description="Create a persisted reaction that invokes a Gerbera tool when a hardware event condition matches.",
            tool_function=create_reaction,
            annotations=ToolAnnotations(
                title="Create reaction", readOnlyHint=False, openWorldHint=False
            ),
        )
        self.register_tool(
            name="list_reactions",
            description="List active reactions and their runtime status.",
            tool_function=list_reactions,
            annotations=ToolAnnotations(
                title="List reactions", readOnlyHint=True, openWorldHint=False
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

    def event_catalog(
        self,
    ) -> dict[str, dict[str, dict[str, dict[str, object]]]]:
        catalog: dict[str, dict[str, dict[str, dict[str, object]]]] = {}

        for event_key, event in self.event_bus.events.items():
            event_type = event_key.event_type
            microcontroller_id = event_key.microcontroller_id
            event_name = event_key.event_name
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

    def register_reaction_catalog_tool(self) -> None:
        def list_reaction_events() -> dict[
            str, dict[str, dict[str, dict[str, object]]]
        ]:
            return self.event_catalog()

        self.register_tool(
            name="list_reaction_events",
            description="List the registered hardware events that can be used when creating reactions.",
            tool_function=list_reaction_events,
            annotations=ToolAnnotations(
                title="List events available for reactions",
                readOnlyHint=True,
                openWorldHint=False,
            ),
        )

    def register_remote_resources(self) -> None:
        @self.app.resource("gerbera://manifest", mime_type="application/json")
        def runtime_manifest() -> str:
            return RuntimeManifest(
                instance_id=self.hardware_system.id,
            ).model_dump_json()

        @self.app.resource("gerbera://hardware/state", mime_type="application/json")
        def hardware_state() -> str:
            return json.dumps(self.hardware_runtime.get_state_store())

        @self.app.resource("gerbera://environment/state", mime_type="application/json")
        def environment_state() -> str:
            return json.dumps(self.model_runtime.get_model_state())

        @self.app.resource("gerbera://hardware", mime_type="application/json")
        def hardware_description() -> str:
            return json.dumps(
                {
                    "name": self.hardware_system.name,
                    "description": self.hardware_system.description,
                    "boards": [
                        {
                            "id": board.microcontroller_id,
                            "name": board.name,
                            "fqbn": board.definition.fqbn,
                            "devices": [
                                {
                                    "name": connection.name,
                                    "type": connection.component_type,
                                }
                                for connection in board.connections
                            ],
                        }
                        for board in self.hardware_plan.boards
                    ],
                    "cameras": [camera.name for camera in self.hardware_system.cameras],
                }
            )

    def register_hardware_state_tool(self) -> None:
        self.register_tool(
            name="get_current_hardware_state",
            description="Read the current hardware state memory.",
            tool_function=self.hardware_runtime.get_state_store,
            annotations=ToolAnnotations(
                title="Get current hardware state", readOnlyHint=True
            ),
        )

    def register_environment_state_tool(self) -> None:
        self.register_tool(
            name="get_current_environment_state",
            description="Read the current environment state from model outputs.",
            tool_function=self.model_runtime.get_model_state,
            annotations=ToolAnnotations(
                title="Get current environment state", readOnlyHint=True
            ),
        )

    def command_annotations(
        self, connection: Connection, command: CommandConfig
    ) -> ToolAnnotations:
        builder = get_device_builder(connection.component_type)
        builder.validate_required_pins(connection)
        annotations = builder.command_config(command.method, connection).annotations
        return ToolAnnotations(
            title=builder.render(annotations.title, connection),
            readOnlyHint=annotations.read_only_hint,
            openWorldHint=annotations.open_world_hint,
        )
