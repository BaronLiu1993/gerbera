from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import cached_property
from typing import ClassVar, TypeAlias

import cv2
import numpy as np
import yaml
from numpy.typing import NDArray

from gerbera_sdk.inference.frame import BoundingBox, Frame
from gerbera_sdk.inference.model_types import ObjectDetectionModelProviderEnum
from gerbera_sdk.inference.models.neural_network.object_detection.object_detection_schema import (
    ObjectDetectionModelManifestSchema,
    PerceptionObjectModel,
)
from gerbera_sdk.paths import MODELS_PATH


@dataclass
class ObjectDetectionAdapter(ABC):
    model_source: str

    @cached_property
    def model(self) -> cv2.dnn.Net:
        return cv2.dnn.readNetFromONNX(str(MODELS_PATH / self.model_source))

    @cached_property
    def manifest(self) -> ObjectDetectionModelManifestSchema:
        manifest_path = MODELS_PATH / f"{self.model_source}.yaml"
        manifest_data = yaml.safe_load(manifest_path.read_text())
        manifest = ObjectDetectionModelManifestSchema.model_validate(
            manifest_data
        )
        return manifest

    @abstractmethod
    def validate_output(self, predictions: NDArray[np.floating]) -> None:
        pass

    @abstractmethod
    def detect(self, frame: Frame) -> list[PerceptionObjectModel]:
        pass

    @abstractmethod
    def decode(
        self,
        predictions: NDArray[np.floating],
    ) -> list[PerceptionObjectModel]:
        pass


@dataclass
class Yolov5ModelAdapter(ObjectDetectionAdapter):
    confidence_threshold: float
    iou_threshold: float
    max_detections: int

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


class Yolov8ModelAdapter(ObjectDetectionAdapter):
    MODEL_FORMAT: ClassVar[ObjectDetectionModelProviderEnum] = (
        ObjectDetectionModelProviderEnum.YOLOV8
    )

    def validate_output(self, predictions: NDArray[np.floating]) -> None:
        pass

    def decode(
        self,
        predictions: NDArray[np.floating],
    ) -> list[PerceptionObjectModel]:
        pass

    def detect(self, frame: Frame) -> list[PerceptionObjectModel]:
        pass


ObjectDetectionModelAdapters: TypeAlias = Yolov5ModelAdapter

OBJECT_DETECTION_MODEL_REGISTRY = {
    ObjectDetectionModelProviderEnum.YOLOV5: Yolov5ModelAdapter,
}
