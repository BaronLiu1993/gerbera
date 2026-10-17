from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import cached_property
from typing import ClassVar

import cv2
import numpy as np
from numpy.typing import NDArray

from gerbera_sdk.inference.frame import Frame
from gerbera_sdk.inference.model_types import ObjectDepthModelProviderEnum
from gerbera_sdk.inference.models.neural_network.local_model_files import (
    LocalModelFiles,
)
from gerbera_sdk.inference.models.neural_network.object_depth.object_depth_schema import (
    DepthMapModel,
    ObjectDepthModelManifestSchema,
)


DEFAULT_MAXIMUM_DEPTH_VALUES = 65_536


@dataclass
class ObjectDepthAdapter(ABC):
    model_directory: str
    manifest: ObjectDepthModelManifestSchema
    maximum_output_values: int = DEFAULT_MAXIMUM_DEPTH_VALUES

    provider: ClassVar[ObjectDepthModelProviderEnum]

    @cached_property
    def files(self) -> LocalModelFiles:
        return LocalModelFiles(self.model_directory)

    def validate_configuration(self) -> None:
        if self.manifest.model_format is not self.provider:
            raise ValueError(
                f"Depth manifest format {self.manifest.model_format.value} does "
                f"not match adapter {self.provider.value}"
            )
        self.files.weights_path(self.manifest.weights)

    @cached_property
    def model(self) -> cv2.dnn.Net:
        return cv2.dnn.readNetFromONNX(
            str(self.files.weights_path(self.manifest.weights))
        )

    def estimate(self, frame: Frame) -> DepthMapModel:
        self.model.setInput(self.build_input(frame))
        prediction = np.asarray(self.model.forward())
        depth_values = self.decode(prediction, frame.image.shape[:2])
        return DepthMapModel(
            width=depth_values.shape[1],
            height=depth_values.shape[0],
            values=depth_values.tolist(),
            minimum_value=float(depth_values.min()),
            maximum_value=float(depth_values.max()),
            value_type=self.manifest.output.value_type,
            unit=self.manifest.output.unit,
        )

    def build_input(self, frame: Frame) -> NDArray[np.float32]:
        model_input = self.manifest.input
        blob = cv2.dnn.blobFromImage(
            frame.image,
            scalefactor=model_input.scale_factor,
            size=(model_input.width, model_input.height),
            swapRB=model_input.swap_red_blue,
            crop=False,
        )
        mean = np.asarray(
            model_input.mean,
            dtype=np.float32,
        ).reshape(1, 3, 1, 1)
        standard_deviation = np.asarray(
            model_input.standard_deviation,
            dtype=np.float32,
        ).reshape(1, 3, 1, 1)
        return np.asarray(
            (blob - mean) / standard_deviation,
            dtype=np.float32,
        )

    def decode(
        self,
        prediction: NDArray[np.generic],
        frame_shape: tuple[int, int],
    ) -> NDArray[np.float32]:
        depth_values = self.extract_depth_map(prediction)
        output_height, output_width = self.bounded_output_shape(frame_shape)
        resized = cv2.resize(
            depth_values,
            (output_width, output_height),
            interpolation=cv2.INTER_CUBIC,
        )
        result = np.asarray(resized, dtype=np.float32)
        if not np.isfinite(result).all():
            raise ValueError("Depth output contains NaN or infinite values")
        return result

    def bounded_output_shape(
        self,
        frame_shape: tuple[int, int],
    ) -> tuple[int, int]:
        frame_height, frame_width = frame_shape
        frame_value_count = frame_height * frame_width
        if frame_value_count <= self.maximum_output_values:
            return frame_shape

        scale = np.sqrt(self.maximum_output_values / frame_value_count)
        output_height = max(1, int(frame_height * scale))
        output_width = max(1, int(frame_width * scale))
        return output_height, output_width

    @abstractmethod
    def extract_depth_map(
        self,
        prediction: NDArray[np.generic],
    ) -> NDArray[np.float32]:
        raise NotImplementedError

    @staticmethod
    def extract_single_channel_map(
        prediction: NDArray[np.generic],
    ) -> NDArray[np.float32]:
        squeezed = np.squeeze(prediction)
        if squeezed.ndim != 2:
            raise ValueError(
                "Depth model must produce one two-dimensional depth map; "
                f"received shape {prediction.shape}"
            )
        if not np.issubdtype(squeezed.dtype, np.floating):
            raise ValueError(
                f"Depth output must be floating point; received {squeezed.dtype}"
            )
        return np.asarray(squeezed, dtype=np.float32)


@dataclass
class MidasModelAdapter(ObjectDepthAdapter):
    provider: ClassVar[ObjectDepthModelProviderEnum] = (
        ObjectDepthModelProviderEnum.MIDAS
    )

    def extract_depth_map(
        self,
        prediction: NDArray[np.generic],
    ) -> NDArray[np.float32]:
        return self.extract_single_channel_map(prediction)


@dataclass
class DepthAnythingModelAdapter(ObjectDepthAdapter):
    provider: ClassVar[ObjectDepthModelProviderEnum] = (
        ObjectDepthModelProviderEnum.DEPTH_ANYTHING
    )

    def extract_depth_map(
        self,
        prediction: NDArray[np.generic],
    ) -> NDArray[np.float32]:
        return self.extract_single_channel_map(prediction)


OBJECT_DEPTH_MODEL_REGISTRY: dict[
    ObjectDepthModelProviderEnum,
    type[ObjectDepthAdapter],
] = {
    ObjectDepthModelProviderEnum.MIDAS: MidasModelAdapter,
    ObjectDepthModelProviderEnum.DEPTH_ANYTHING: DepthAnythingModelAdapter,
}
