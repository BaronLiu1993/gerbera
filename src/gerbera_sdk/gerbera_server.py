import base64
from collections import Counter
from dataclasses import dataclass
from inspect import Parameter, Signature
from typing import Annotated, Any, Callable, Literal

from fastmcp import FastMCP
from gerbera_protocol import RuntimeManifest
from mcp.types import ToolAnnotations
from pydantic import Field, TypeAdapter

from gerbera_sdk.camera_runtime import CameraRuntime
from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.reactions.reaction_bus import ReactionBus
from gerbera_sdk.events.reactions.reaction_executor import ReactionActionRegistry
from gerbera_sdk.events.reactions.reaction_schema import (
    CreateReactionSchema,
    DeleteReactionResultSchema,
    DeleteReactionSchema,
    ReactionSchema,
)
from gerbera_sdk.config.firmware_config import load_firmware_config
from gerbera_sdk.latest_runtime import HardwareRuntime
from gerbera_sdk.inference import VisionLanguageModelFrameEnvironment
from gerbera_sdk.inference.model_descriptor import ModelDescriptor
from gerbera_sdk.inference.model_types import (
    ModelCatalogEntry,
    ModelCatalogType,
    SubscribedCameraCatalogEntry,
)
from gerbera_sdk.models.hardware.camera import Frame
from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.camera import Frame
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.runtime.boards.board_runtime import BoardRuntime

def encode_camera_frame(frame: Frame) -> str:
    return base64.b64encode(frame.encode()).decode("ascii")

import json


@dataclass
class GerberaServer:
    hardware_plan: HardwarePlan
    hardware_runtime: HardwareRuntime
    board_runtime: BoardRuntime
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

    def register_hardware_tools(self) -> None:
        boards = self.hardware_system.microcontrollers
        connection_ids = Counter(
            connection.connection_id
            for board in boards
            for connection in board.connections
        )
        for board in boards:
            for connection in board.connections:
                tool_id = connection.connection_id
                if connection_ids[tool_id] > 1:
                    tool_id = f"{board.microcontroller_id}_{tool_id}"
                self.register_connection_tools(connection, f"write_{tool_id}")

    def register_connection_tools(self, connection: Connection, tool_name: str | None = None) -> None:
        config = load_firmware_config(connection.component_type)
        write = config.get("write")
        supports_stream = connection.supports_streaming and "stream" in config
        if write is None and not supports_stream:
            return

        specs = dict(write["params"]) if write is not None else {}
        required = [name for name, spec in specs.items() if spec["required"]]
        if supports_stream:
            specs["stream_enabled"] = {"choices": [0, 1], "required": write is None}

        parameters = []
        adapters = {}
        for name, spec in specs.items():
            annotation: Any
            if "choices" in spec:
                annotation = Literal[tuple(spec["choices"])]
            else:
                annotation = Annotated[
                    int, Field(strict=True, ge=spec.get("minimum"), le=spec.get("maximum"))
                ]
            adapters[name] = TypeAdapter(annotation)

            default = Parameter.empty
            if not spec["required"] or (supports_stream and write is not None):
                default = None
                annotation |= None
            parameters.append(
                Parameter(name, Parameter.KEYWORD_ONLY, default=default, annotation=annotation)
            )
        signature = Signature(parameters, return_annotation=dict[str, bool])

        def write_tool(**values: int | None) -> dict[str, bool]:
            arguments = signature.bind(**values).arguments
            fields = {}
            for name, value in arguments.items():
                if value is not None:
                    fields[name] = adapters[name].validate_python(value, strict=True)

            if "stream_enabled" in fields:
                if len(fields) != 1:
                    raise ValueError("Send stream control as its own write")
            elif not fields or any(name not in fields for name in required):
                raise ValueError("Supply the required device settings")

            self.board_runtime.write_connection(connection, fields)
            return {"sent": True}

        write_tool.__signature__ = signature
        write_tool.__annotations__ = {
            parameter.name: parameter.annotation for parameter in parameters
        }
        write_tool.__annotations__["return"] = signature.return_annotation
        description = f"Write settings for {connection.connection_id}."
        if supports_stream:
            description += " Set stream_enabled to 1 to start streaming or 0 to stop."

        result_field = write["response_field"] if write is not None else "stream_enabled"
        state_key = (connection.microcontroller_id, connection.connection_id, result_field)
        self.register_tool(
            name=tool_name or f"write_{connection.connection_id}",
            description=description,
            tool_function=write_tool,
            annotations=ToolAnnotations(
                title=f"Write {connection.connection_id}",
                readOnlyHint=False,
                openWorldHint=False,
            ),
            meta={"key": self.hardware_runtime.get_state_key_label(state_key)},
        )

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
                        camera_id=camera_key,
                        image_count=image_count,
                        interval_seconds=interval_seconds,
                    )
                    encoded_frames: list[str] = []
                    for frame in frames:
                        encoded_frames.append(encode_camera_frame(frame))
                    return encoded_frames

                return capture_frames_from_camera

            self.register_tool(
                name=f"capture_frames_from_{camera.camera_id}",
                description=(
                    f"Capture one or more current images from {camera.camera_id}. "
                    "image_count controls the batch size and interval_seconds controls "
                    "the delay between images. Returns Base64-encoded "
                    f"{camera.output_format.removeprefix('.').upper()} images."
                ),
                tool_function=build_capture_frames_tool(camera_key),
                annotations=ToolAnnotations(
                    title=f"Capture frames from {camera.camera_id}",
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
                            name=camera.camera_id,
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
                    "cameras": [camera.camera_id for camera in self.hardware_system.cameras],
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
