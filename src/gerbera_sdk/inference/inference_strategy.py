from abc import ABC, abstractmethod
from typing import ClassVar, Literal, Protocol

from gerbera_sdk.inference import Inference
from gerbera_sdk.inference.models.neural_network.object_detection.object_detection_model_inference import (
    ObjectDetectionModelInference,
)
from gerbera_sdk.inference.models.neural_network.object_detection.object_detection_schema import (
    PerceptionStateModel,
)
from gerbera_sdk.inference.models.vision_language_model.vision_language_model_inference import (
    VisionLanguageModelInference,
)
from gerbera_sdk.inference.models.vision_language_model.vision_language_model_schema import (
    VisionLanguageModelFrameEnvironment,
)

InferenceType = Literal["analysis", "object_detection"]
ModelStreamAction = Literal["on", "off"]
InferenceStrategyResult = (
    list[PerceptionStateModel]
    | PerceptionStateModel
    | VisionLanguageModelFrameEnvironment
    | str
)


class InferenceOutputRuntime(Protocol):
    def write_model_output_for_subscribed_cameras(
        self,
        model_id: str,
        inference_type: InferenceType,
        model_output: object,
    ) -> None:
        pass


class SingleInferenceStrategy(ABC):
    inference_type: ClassVar[InferenceType]
    inference_class: ClassVar[type[Inference]]

    def supports(
        self,
        *,
        inference_type: InferenceType,
        inference: Inference,
    ) -> bool:
        return (
            inference_type == self.inference_type
            and isinstance(inference, self.inference_class)
        )

    @abstractmethod
    def run(
        self,
        *,
        runtime: InferenceOutputRuntime,
        model_id: str,
        inference: Inference,
        inference_input: str | list[str],
        prompt: str | None,
    ) -> InferenceStrategyResult:
        pass

    def require_prompt(self, prompt: str | None, message: str) -> str:
        if prompt is None:
            raise ValueError(message)
        return prompt

    def require_base64_frames(
        self,
        inference_input: str | list[str],
        message: str,
    ) -> list[str]:
        if not isinstance(inference_input, list) or not all(
            isinstance(frame, str) for frame in inference_input
        ):
            raise TypeError(message)
        if not inference_input:
            raise ValueError("At least one frame is required for inference")
        return inference_input

    def write_model_output(
        self,
        *,
        runtime: InferenceOutputRuntime,
        model_id: str,
        inference_type: InferenceType,
        model_output: object,
    ) -> None:
        runtime.write_model_output_for_subscribed_cameras(
            model_id=model_id,
            inference_type=inference_type,
            model_output=model_output,
        )


class ModelStreamStrategy(ABC):
    inference_class: ClassVar[type[Inference]]
    requires_prompt_to_turn_on: ClassVar[bool] = False

    def supports(self, inference: Inference) -> bool:
        return isinstance(inference, self.inference_class)

    def run(
        self,
        *,
        inference: Inference,
        action: ModelStreamAction,
        prompt: str | None,
    ) -> None:
        if action == "on":
            self.turn_on(inference=inference, prompt=prompt)
            return
        self.turn_off(inference)

    @abstractmethod
    def turn_on(self, *, inference: Inference, prompt: str | None) -> None:
        pass

    def turn_off(self, inference: Inference) -> None:
        if not inference.is_running:
            return
        inference.turn_off_prediction_loop()


class ObjectDetectionSingleInferenceStrategy(SingleInferenceStrategy):
    inference_type = "object_detection"
    inference_class = ObjectDetectionModelInference

    def run(
        self,
        *,
        runtime: InferenceOutputRuntime,
        model_id: str,
        inference: Inference,
        inference_input: str | list[str],
        prompt: str | None,
    ) -> list[PerceptionStateModel] | PerceptionStateModel:
        if not isinstance(inference, ObjectDetectionModelInference):
            raise TypeError(
                "Object detection strategy requires object detection inference"
            )
        if isinstance(inference_input, str):
            return inference.predict(inference_input)
        if not isinstance(inference_input, list) or not all(
            isinstance(camera_id, str) for camera_id in inference_input
        ):
            raise TypeError(
                "Object detection inference requires one camera ID or "
                "a list of camera IDs"
            )
        if not inference_input:
            raise ValueError("At least one camera ID is required for inference")
        return inference.predict_many(inference_input)


class ObjectDetectionModelStreamStrategy(ModelStreamStrategy):
    inference_class = ObjectDetectionModelInference

    def turn_on(self, *, inference: Inference, prompt: str | None) -> None:
        if not isinstance(inference, ObjectDetectionModelInference):
            raise TypeError("Object detection stream requires object detection inference")
        if inference.is_running:
            return
        inference.turn_on_prediction_loop()


class VisionLanguageModelObjectDetectionSingleInferenceStrategy(
    SingleInferenceStrategy
):
    inference_type = "object_detection"
    inference_class = VisionLanguageModelInference

    def run(
        self,
        *,
        runtime: InferenceOutputRuntime,
        model_id: str,
        inference: Inference,
        inference_input: str | list[str],
        prompt: str | None,
    ) -> VisionLanguageModelFrameEnvironment:
        if not isinstance(inference, VisionLanguageModelInference):
            raise TypeError(
                "Vision language strategy requires vision language inference"
            )
        prompt = self.require_prompt(
            prompt,
            "Vision language model inference requires a prompt",
        )
        frames = self.require_base64_frames(
            inference_input,
            (
                "Vision language model inference requires a list of "
                "Base64 image strings"
            ),
        )

        result = inference.predict(frames, prompt=prompt)
        self.write_model_output(
            runtime=runtime,
            model_id=model_id,
            inference_type=self.inference_type,
            model_output=result,
        )
        return result


class VisionLanguageModelStreamStrategy(ModelStreamStrategy):
    inference_class = VisionLanguageModelInference
    requires_prompt_to_turn_on = True

    def turn_on(self, *, inference: Inference, prompt: str | None) -> None:
        if not isinstance(inference, VisionLanguageModelInference):
            raise TypeError("Vision language stream requires vision language inference")
        if inference.is_running:
            return
        if prompt is None:
            raise ValueError("Vision language model prediction loop requires a prompt")
        inference.turn_on_prediction_loop(prompt=prompt)


class VisionLanguageModelAnalysisSingleInferenceStrategy(SingleInferenceStrategy):
    inference_type = "analysis"
    inference_class = VisionLanguageModelInference

    def run(
        self,
        *,
        runtime: InferenceOutputRuntime,
        model_id: str,
        inference: Inference,
        inference_input: str | list[str],
        prompt: str | None,
    ) -> str:
        if not isinstance(inference, VisionLanguageModelInference):
            raise TypeError(
                "Vision language analysis strategy requires vision language inference"
            )
        prompt = self.require_prompt(prompt, "Scene analysis requires a prompt")
        frames = self.require_base64_frames(
            inference_input,
            "Scene analysis requires a list of Base64 image strings",
        )

        result = inference.analyze_scene(frames, prompt=prompt)
        self.write_model_output(
            runtime=runtime,
            model_id=model_id,
            inference_type=self.inference_type,
            model_output=result,
        )
        return result


SINGLE_INFERENCE_STRATEGIES: tuple[SingleInferenceStrategy, ...] = (
    ObjectDetectionSingleInferenceStrategy(),
    VisionLanguageModelObjectDetectionSingleInferenceStrategy(),
    VisionLanguageModelAnalysisSingleInferenceStrategy(),
)

MODEL_STREAM_STRATEGIES: tuple[ModelStreamStrategy, ...] = (
    ObjectDetectionModelStreamStrategy(),
    VisionLanguageModelStreamStrategy(),
)
