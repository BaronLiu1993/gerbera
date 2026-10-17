from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import cached_property
from typing import ClassVar

import cv2
import numpy as np
from numpy.typing import NDArray

from gerbera_sdk.inference.frame import BoundingBox, Frame
from gerbera_sdk.inference.model_types import ObjectDetectionModelProviderEnum
from gerbera_sdk.inference.models.neural_network.local_model_files import (
    LocalModelFiles,
)
from gerbera_sdk.inference.models.neural_network.object_detection.object_detection_schema import (
    ObjectDetectionModelManifestSchema,
    PerceptionObjectModel,
)


@dataclass
class ObjectDetectionAdapter(ABC):
    model_directory: str
    manifest: ObjectDetectionModelManifestSchema

    provider: ClassVar[ObjectDetectionModelProviderEnum]

    @cached_property
    def files(self) -> LocalModelFiles:
        return LocalModelFiles(self.model_directory)

    @cached_property
    def model(self) -> cv2.dnn.Net:
        return cv2.dnn.readNetFromONNX(
            str(self.files.weights_path(self.manifest.weights))
        )

    def validate_configuration(self) -> None:
        if self.manifest.model_format is not self.provider:
            raise ValueError(
                f"Detection manifest format {self.manifest.model_format.value} "
                f"does not match adapter {self.provider.value}"
            )
        self.files.weights_path(self.manifest.weights)

    @abstractmethod
    def validate_output(self, predictions: NDArray[np.floating]) -> None:
        raise NotImplementedError

    @abstractmethod
    def detect(self, frame: Frame) -> list[PerceptionObjectModel]:
        raise NotImplementedError

    @abstractmethod
    def decode(
        self,
        predictions: NDArray[np.floating],
    ) -> list[PerceptionObjectModel]:
        raise NotImplementedError


@dataclass
class Yolov5ModelAdapter(ObjectDetectionAdapter):
    provider: ClassVar[ObjectDetectionModelProviderEnum] = (
        ObjectDetectionModelProviderEnum.YOLOV5
    )
    confidence_threshold: float = 0.25
    iou_threshold: float = 0.45
    max_detections: int = 300

    def validate_output(self, predictions: NDArray[np.floating]) -> None:
        value_count = 5 + len(self.manifest.output.class_names)
        expected_shape = (
            1,
            self.manifest.output.prediction_count,
            value_count,
        )

        if predictions.shape != expected_shape:
            raise ValueError(
                "Unexpected YOLOv5 output shape: "
                f"expected {expected_shape}, received {predictions.shape}"
            )
        if not np.isfinite(predictions).all():
            raise ValueError("YOLOv5 output contains NaN or infinite values")

    def decode(
        self,
        predictions: NDArray[np.floating],
    ) -> list[PerceptionObjectModel]:
        self.validate_output(predictions)

        candidates = predictions[0]
        candidates = candidates[
            candidates[:, 4] >= self.confidence_threshold
        ]
        if len(candidates) == 0:
            return []

        class_scores = candidates[:, 5:]
        class_ids = np.argmax(class_scores, axis=1)
        confidences = (
            candidates[:, 4]
            * class_scores[np.arange(len(candidates)), class_ids]
        )

        confident = confidences >= self.confidence_threshold
        candidates = candidates[confident]
        class_ids = class_ids[confident]
        confidences = confidences[confident]
        if len(candidates) == 0:
            return []

        center_x = candidates[:, 0]
        center_y = candidates[:, 1]
        width = candidates[:, 2]
        height = candidates[:, 3]
        boxes = np.column_stack(
            (
                center_x - width / 2,
                center_y - height / 2,
                width,
                height,
            )
        )

        kept_indices: list[int] = []
        for class_id in np.unique(class_ids):
            class_indices = np.flatnonzero(class_ids == class_id)
            class_boxes = [boxes[index].tolist() for index in class_indices]
            class_confidences = [
                float(confidences[index]) for index in class_indices
            ]

            selected = cv2.dnn.NMSBoxes(
                class_boxes,
                class_confidences,
                self.confidence_threshold,
                self.iou_threshold,
            )
            for selected_index in np.asarray(selected).reshape(-1):
                kept_indices.append(
                    int(class_indices[int(selected_index)])
                )

        kept_indices.sort(
            key=lambda index: float(confidences[index]),
            reverse=True,
        )

        detections: list[PerceptionObjectModel] = []
        for index in kept_indices[: self.max_detections]:
            left, top, box_width, box_height = boxes[index]
            input_width = self.manifest.input.width
            input_height = self.manifest.input.height
            xmin = float(np.clip(left / input_width, 0.0, 1.0))
            ymin = float(np.clip(top / input_height, 0.0, 1.0))
            xmax = float(
                np.clip((left + box_width) / input_width, 0.0, 1.0)
            )
            ymax = float(
                np.clip((top + box_height) / input_height, 0.0, 1.0)
            )

            if xmin >= xmax or ymin >= ymax:
                continue

            class_id = int(class_ids[index])
            detections.append(
                PerceptionObjectModel(
                    class_id=class_id,
                    class_name=self.manifest.output.class_names[class_id],
                    confidence=float(confidences[index]),
                    bounding_box=BoundingBox(
                        xmin=xmin,
                        xmax=xmax,
                        ymin=ymin,
                        ymax=ymax,
                    ),
                )
            )

        return detections

    def detect(self, frame: Frame) -> list[PerceptionObjectModel]:
        input_size = (
            self.manifest.input.width,
            self.manifest.input.height,
        )
        blob = cv2.dnn.blobFromImage(
            frame.image,
            scalefactor=1 / 255.0,
            size=input_size,
            swapRB=True,
            crop=False,
        )
        self.model.setInput(blob)
        predictions = self.model.forward()
        return self.decode(predictions)

OBJECT_DETECTION_MODEL_REGISTRY = {
    ObjectDetectionModelProviderEnum.YOLOV5: Yolov5ModelAdapter,
}
