from typing import ClassVar

from gerbera_sdk.inference.frame import Frame
from gerbera_sdk.inference.models.neural_network.object_depth.object_depth_model_inference import (
    ObjectDepthModelInference,
)
from gerbera_sdk.inference.models.neural_network.object_depth.object_depth_schema import (
    ObjectDepthStateModel,
)
from gerbera_sdk.inference.models.neural_network.object_detection.object_detection_model_inference import (
    ObjectDetectionModelInference,
)
from gerbera_sdk.inference.models.neural_network.object_detection.object_detection_schema import (
    PerceptionStateModel,
)
from gerbera_sdk.inference.models.neural_network.object_segmentation.object_segmentation_model_inference import (
    ObjectSegmentationModelInference,
)
from gerbera_sdk.inference.models.neural_network.object_segmentation.object_segmentation_schema import (
    ObjectSegmentationStateModel,
)
from gerbera_sdk.inference.models.vision_language_model.vision_language_model_inference import (
    VisionLanguageModelInference,
)
from gerbera_sdk.inference.models.vision_language_model.vision_language_model_schema import (
    VisionLanguageModelFrameEnvironment,
)


class ObjectDetectionRuntimeStrategy:
    output_types: ClassVar[dict[str, type]] = {
        "object_detection": PerceptionStateModel,
    }
    stream_output_name = "object_detection"

    @staticmethod
    def perform(
        inference: ObjectDetectionModelInference,
        frame: Frame,
    ) -> PerceptionStateModel:
        return inference.predict(frame)

    @staticmethod
    def resolve_stream_prompt(
        inference: ObjectDetectionModelInference,
        prompt: str | None,
    ) -> None:
        return None

    def predict_stream(
        self,
        inference: ObjectDetectionModelInference,
        frame: Frame,
        prompt: str | None,
    ) -> PerceptionStateModel:
        return self.perform(inference, frame)

    @staticmethod
    def default_stream_prompt(
        inference: ObjectDetectionModelInference,
    ) -> None:
        return None


class ObjectDepthRuntimeStrategy:
    output_types: ClassVar[dict[str, type]] = {
        "object_depth": ObjectDepthStateModel,
    }
    stream_output_name = "object_depth"

    @staticmethod
    def perform(
        inference: ObjectDepthModelInference,
        frame: Frame,
    ) -> ObjectDepthStateModel:
        return inference.predict(frame)

    @staticmethod
    def resolve_stream_prompt(
        inference: ObjectDepthModelInference,
        prompt: str | None,
    ) -> None:
        return None

    def predict_stream(
        self,
        inference: ObjectDepthModelInference,
        frame: Frame,
        prompt: str | None,
    ) -> ObjectDepthStateModel:
        return self.perform(inference, frame)

    @staticmethod
    def default_stream_prompt(
        inference: ObjectDepthModelInference,
    ) -> None:
        return None


class ObjectSegmentationRuntimeStrategy:
    output_types: ClassVar[dict[str, type]] = {
        "object_segmentation": ObjectSegmentationStateModel,
    }
    stream_output_name = "object_segmentation"

    @staticmethod
    def perform(
        inference: ObjectSegmentationModelInference,
        frame: Frame,
    ) -> ObjectSegmentationStateModel:
        return inference.predict(frame)

    @staticmethod
    def resolve_stream_prompt(
        inference: ObjectSegmentationModelInference,
        prompt: str | None,
    ) -> None:
        return None

    def predict_stream(
        self,
        inference: ObjectSegmentationModelInference,
        frame: Frame,
        prompt: str | None,
    ) -> ObjectSegmentationStateModel:
        return self.perform(inference, frame)

    @staticmethod
    def default_stream_prompt(
        inference: ObjectSegmentationModelInference,
    ) -> None:
        return None


class VisionLanguageRuntimeStrategy:
    output_types: ClassVar[dict[str, type]] = {
        "locate_object": VisionLanguageModelFrameEnvironment,
        "scene_analysis": str,
    }
    stream_output_name = "locate_object"

    @staticmethod
    def locate_objects(
        inference: VisionLanguageModelInference,
        frames: list[str],
        prompt: str,
    ) -> VisionLanguageModelFrameEnvironment:
        result = inference.predict(
            frames,
            operation="locate_object",
            prompt=prompt,
        )
        if not isinstance(result, VisionLanguageModelFrameEnvironment):
            raise TypeError("Object location inference returned an invalid output")
        return result

    @staticmethod
    def analyze_scene(
        inference: VisionLanguageModelInference,
        frames: list[str],
        prompt: str,
    ) -> str:
        result = inference.predict(
            frames,
            operation="scene_analysis",
            prompt=prompt,
        )
        if not isinstance(result, str):
            raise TypeError("Scene analysis inference returned an invalid output")
        return result

    def predict_stream(
        self,
        inference: VisionLanguageModelInference,
        frame: Frame,
        prompt: str | None,
    ) -> VisionLanguageModelFrameEnvironment:
        resolved_prompt = self.resolve_stream_prompt(inference, prompt)
        return self.locate_objects(
            inference,
            [frame.to_base64_string()],
            resolved_prompt,
        )

    @staticmethod
    def resolve_stream_prompt(
        inference: VisionLanguageModelInference,
        prompt: str | None,
    ) -> str:
        if prompt is None:
            raise ValueError("Vision language model stream requires a prompt")
        return prompt

    @staticmethod
    def default_stream_prompt(
        inference: VisionLanguageModelInference,
    ) -> str:
        return inference.user_prompt


ModelRuntimeStrategy = (
    ObjectDepthRuntimeStrategy
    | ObjectDetectionRuntimeStrategy
    | ObjectSegmentationRuntimeStrategy
    | VisionLanguageRuntimeStrategy
)

MODEL_RUNTIME_STRATEGIES: dict[type, ModelRuntimeStrategy] = {
    ObjectDepthModelInference: ObjectDepthRuntimeStrategy(),
    ObjectDetectionModelInference: ObjectDetectionRuntimeStrategy(),
    ObjectSegmentationModelInference: ObjectSegmentationRuntimeStrategy(),
    VisionLanguageModelInference: VisionLanguageRuntimeStrategy(),
}
