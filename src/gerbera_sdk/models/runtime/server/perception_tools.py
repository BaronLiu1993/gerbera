from dataclasses import dataclass
from typing import Annotated, Any, Callable

from mcp.types import ToolAnnotations
from pydantic import Field

from gerbera_sdk.models.runtime.server.tool_registry import McpToolRegistry, ToolDefinition
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.runtime.perception.camera_runtime import CameraRuntime
from gerbera_sdk.models.runtime.perception.model_runtime import ModelRuntime
from gerbera_sdk.inference.model_types import (
    ModelCatalogEntry,
    ModelCatalogType,
    SubscribedCameraCatalogEntry,
)
from gerbera_sdk.inference import (
    Inference,
    ObjectDepthModelInference,
    ObjectDetectionModelInference,
    ObjectSegmentationModelInference,
    VisionLanguageModelInference,
    VisionLanguageModelFrameEnvironment,
)

MODEL_CATALOG_TYPES = {
    ObjectDepthModelInference: "object_depth",
    ObjectDetectionModelInference: "object_detection",
    ObjectSegmentationModelInference: "object_segmentation",
    VisionLanguageModelInference: "vision_language_model",
}
FRAME_MODEL_OUTPUT_NAMES = {
    ObjectDepthModelInference: "object_depth",
    ObjectSegmentationModelInference: "object_segmentation",
}


@dataclass
class PerceptionTools:
    tools: McpToolRegistry
    hardware_system: HardwareSystem
    camera_runtime: CameraRuntime
    model_runtime: ModelRuntime

    @staticmethod
    def model_catalog_type(model: Inference) -> ModelCatalogType:
        try:
            return MODEL_CATALOG_TYPES[type(model)]
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

            self.tools.register(ToolDefinition(
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
            ))

    def register_inference_tools(self) -> None:
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

        self.tools.register(ToolDefinition(
            name=f"turn_on_{model.name}",
            description=f"Start continuous inference for {model.name}.",
            tool_function=turn_on_inference,
            annotations=ToolAnnotations(
                title=f"Start continuous inference for {model.name}",
                readOnlyHint=False,
                openWorldHint=isinstance(model, VisionLanguageModelInference),
            ),
        ))
        self.tools.register(ToolDefinition(
            name=f"turn_off_{model.name}",
            description=f"Stop continuous inference for {model.name}.",
            tool_function=turn_off_inference,
            annotations=ToolAnnotations(
                title=f"Stop continuous inference for {model.name}",
                readOnlyHint=False,
                openWorldHint=False,
            ),
        ))

        tool_registrars: dict[type, Callable[[str, Any], None]] = {
            ObjectDepthModelInference: self.register_frame_model_tools,
            ObjectDetectionModelInference: self.register_object_detection_tools,
            ObjectSegmentationModelInference: self.register_frame_model_tools,
            VisionLanguageModelInference: self.register_vision_language_model_tools,
        }
        try:
            registrar = tool_registrars[type(model)]
        except KeyError as error:
            raise ValueError(
                f"Unsupported inference model type: {type(model).__name__}"
            ) from error
        registrar(model_id, model)

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

        self.tools.register(ToolDefinition(
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
        ))
        self.tools.register(ToolDefinition(
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
        ))

    def register_frame_model_tools(
        self,
        model_id: str,
        model: ObjectDepthModelInference | ObjectSegmentationModelInference,
    ) -> None:
        output_name = FRAME_MODEL_OUTPUT_NAMES[type(model)]

        def read_model_output() -> dict[str, object]:
            result = self.model_runtime.read_model_output(
                model_id,
                output_name,
            )
            return result.model_dump(mode="json", exclude={"frame"})

        def predict_with_model() -> dict[str, object]:
            result = self.model_runtime.perform_frame_inference(model_id)
            return result.model_dump(mode="json", exclude={"frame"})

        self.tools.register(ToolDefinition(
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
        ))
        self.tools.register(ToolDefinition(
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
        ))

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

        self.tools.register(ToolDefinition(
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
        ))
        self.tools.register(ToolDefinition(
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
        ))
        self.tools.register(ToolDefinition(
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
        ))
        self.tools.register(ToolDefinition(
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
        ))

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

        self.tools.register(ToolDefinition(
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
        ))
