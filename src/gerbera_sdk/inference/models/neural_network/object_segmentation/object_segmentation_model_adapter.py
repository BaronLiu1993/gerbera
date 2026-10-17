from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import cached_property
from typing import ClassVar

import cv2
import numpy as np
from numpy.typing import NDArray

from gerbera_sdk.inference.frame import BoundingBox, Frame
from gerbera_sdk.inference.model_types import (
    ObjectSegmentationModelProviderEnum,
)
from gerbera_sdk.inference.models.neural_network.local_model_files import (
    LocalModelFiles,
)
from gerbera_sdk.inference.models.neural_network.object_segmentation.object_segmentation_schema import (
    NormalizedPoint,
    ObjectSegmentationModelManifestSchema,
    SegmentationMaskModel,
    SegmentedObjectModel,
)


@dataclass(frozen=True)
class SegmentationCandidates:
    boxes: NDArray[np.float32]
    class_ids: NDArray[np.integer]
    confidences: NDArray[np.float32]
    mask_coefficients: NDArray[np.float32]


@dataclass(frozen=True)
class SegmentationDecodeContext:
    prototypes: NDArray[np.generic]
    frame_shape: tuple[int, int]


@dataclass(frozen=True)
class MaskDecodeRequest:
    coefficients: NDArray[np.float32]
    prototypes: NDArray[np.generic]
    box: NDArray[np.float32]
    frame_shape: tuple[int, int]


@dataclass
class ObjectSegmentationAdapter(ABC):
    model_directory: str
    manifest: ObjectSegmentationModelManifestSchema
    confidence_threshold: float = 0.25
    iou_threshold: float = 0.45
    mask_threshold: float = 0.5
    max_detections: int = 100

    provider: ClassVar[ObjectSegmentationModelProviderEnum]
    class_score_offset: ClassVar[int]

    @cached_property
    def files(self) -> LocalModelFiles:
        return LocalModelFiles(self.model_directory)

    def validate_configuration(self) -> None:
        if self.manifest.model_format is not self.provider:
            raise ValueError(
                f"Segmentation manifest format "
                f"{self.manifest.model_format.value} does not match adapter "
                f"{self.provider.value}"
            )
        self.files.weights_path(self.manifest.weights)

    @cached_property
    def model(self) -> cv2.dnn.Net:
        return cv2.dnn.readNetFromONNX(
            str(self.files.weights_path(self.manifest.weights))
        )

    def segment(self, frame: Frame) -> list[SegmentedObjectModel]:
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
        self.model.setInput(np.asarray(blob - mean, dtype=np.float32))
        output_names = [
            self.manifest.output.prediction_output_name,
            self.manifest.output.prototype_output_name,
        ]
        predictions, prototypes = self.model.forward(output_names)
        return self.decode(
            np.asarray(predictions),
            np.asarray(prototypes),
            frame.image.shape[:2],
        )

    def decode(
        self,
        predictions: NDArray[np.generic],
        prototypes: NDArray[np.generic],
        frame_shape: tuple[int, int],
    ) -> list[SegmentedObjectModel]:
        prediction_rows = self.prepare_prediction_rows(predictions)
        self.validate_outputs(prediction_rows, prototypes)
        candidates = self.build_candidates(prediction_rows)
        if len(candidates.boxes) == 0:
            return []
        kept_indices = [
            index
            for index in self.select_candidates(candidates)
            if self.box_intersects_input(candidates.boxes[index])
        ][: self.max_detections]
        context = SegmentationDecodeContext(prototypes, frame_shape)
        return [
            self.build_segmented_object(
                candidates,
                context,
                index,
            )
            for index in kept_indices
        ]

    @abstractmethod
    def prepare_prediction_rows(
        self,
        predictions: NDArray[np.generic],
    ) -> NDArray[np.float32]:
        raise NotImplementedError

    @abstractmethod
    def confidence_scores(
        self,
        rows: NDArray[np.float32],
        class_scores: NDArray[np.float32],
        class_ids: NDArray[np.integer],
    ) -> NDArray[np.float32]:
        raise NotImplementedError

    def validate_outputs(
        self,
        prediction_rows: NDArray[np.float32],
        prototypes: NDArray[np.generic],
    ) -> None:
        class_count = len(self.manifest.output.class_names)
        mask_count = self.manifest.output.mask_coefficient_count
        expected_values = self.class_score_offset + class_count + mask_count
        if prediction_rows.ndim != 2 or prediction_rows.shape[1] != expected_values:
            raise ValueError(
                "Unexpected segmentation prediction shape: expected rows with "
                f"{expected_values} values, received {prediction_rows.shape}"
            )
        expected_prototype_shape = (1, mask_count)
        if prototypes.ndim != 4 or prototypes.shape[:2] != expected_prototype_shape:
            raise ValueError(
                "Unexpected segmentation prototype shape: expected "
                f"(1, {mask_count}, height, width), received {prototypes.shape}"
            )
        if not np.issubdtype(prediction_rows.dtype, np.floating):
            raise ValueError("Segmentation predictions must be floating point")
        if not np.issubdtype(prototypes.dtype, np.floating):
            raise ValueError("Segmentation prototypes must be floating point")
        if not np.isfinite(prediction_rows).all() or not np.isfinite(prototypes).all():
            raise ValueError(
                "Segmentation output contains NaN or infinite values"
            )

    def build_candidates(
        self,
        rows: NDArray[np.float32],
    ) -> SegmentationCandidates:
        class_count = len(self.manifest.output.class_names)
        class_end = self.class_score_offset + class_count
        class_scores = rows[:, self.class_score_offset:class_end]
        class_ids = np.argmax(class_scores, axis=1)
        confidences = self.confidence_scores(rows, class_scores, class_ids)
        confident = confidences >= self.confidence_threshold
        rows = rows[confident]
        class_ids = class_ids[confident]
        confidences = confidences[confident]

        centers = rows[:, :2]
        dimensions = rows[:, 2:4]
        boxes = np.column_stack((centers - dimensions / 2, dimensions))
        coefficients = rows[:, class_end:]
        return SegmentationCandidates(
            boxes=np.asarray(boxes, dtype=np.float32),
            class_ids=class_ids,
            confidences=np.asarray(confidences, dtype=np.float32),
            mask_coefficients=np.asarray(coefficients, dtype=np.float32),
        )

    def select_candidates(
        self,
        candidates: SegmentationCandidates,
    ) -> list[int]:
        kept_indices: list[int] = []
        for class_id in np.unique(candidates.class_ids):
            class_indices = np.flatnonzero(candidates.class_ids == class_id)
            selected = cv2.dnn.NMSBoxes(
                [candidates.boxes[index].tolist() for index in class_indices],
                [float(candidates.confidences[index]) for index in class_indices],
                self.confidence_threshold,
                self.iou_threshold,
            )
            for selected_index in np.asarray(selected).reshape(-1):
                kept_indices.append(int(class_indices[int(selected_index)]))
        kept_indices.sort(
            key=lambda index: float(candidates.confidences[index]),
            reverse=True,
        )
        return kept_indices

    def box_intersects_input(self, box: NDArray[np.float32]) -> bool:
        left, top, width, height = box
        return bool(
            width > 0
            and height > 0
            and left < self.manifest.input.width
            and top < self.manifest.input.height
            and left + width > 0
            and top + height > 0
        )

    def build_segmented_object(
        self,
        candidates: SegmentationCandidates,
        context: SegmentationDecodeContext,
        index: int,
    ) -> SegmentedObjectModel:
        bounding_box = self.normalized_bounding_box(candidates.boxes[index])
        mask = self.decode_mask(
            MaskDecodeRequest(
                coefficients=candidates.mask_coefficients[index],
                prototypes=context.prototypes,
                box=candidates.boxes[index],
                frame_shape=context.frame_shape,
            )
        )
        class_id = int(candidates.class_ids[index])
        return SegmentedObjectModel(
            class_id=class_id,
            class_name=self.manifest.output.class_names[class_id],
            confidence=float(candidates.confidences[index]),
            bounding_box=bounding_box,
            mask=mask,
        )

    def normalized_bounding_box(
        self,
        box: NDArray[np.float32],
    ) -> BoundingBox:
        left, top, width, height = box
        input_width = self.manifest.input.width
        input_height = self.manifest.input.height
        xmin = float(np.clip(left / input_width, 0.0, 1.0))
        ymin = float(np.clip(top / input_height, 0.0, 1.0))
        xmax = float(np.clip((left + width) / input_width, 0.0, 1.0))
        ymax = float(np.clip((top + height) / input_height, 0.0, 1.0))
        if xmin >= xmax or ymin >= ymax:
            raise ValueError("Segmentation output contains an empty bounding box")
        return BoundingBox(xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax)

    def decode_mask(
        self,
        request: MaskDecodeRequest,
    ) -> SegmentationMaskModel:
        prototype_values = np.asarray(request.prototypes[0], dtype=np.float32)
        prototype_height, prototype_width = prototype_values.shape[1:]
        logits = request.coefficients @ prototype_values.reshape(
            len(request.coefficients),
            -1,
        )
        probabilities = 1.0 / (1.0 + np.exp(-np.clip(logits, -80, 80)))
        input_size = (self.manifest.input.width, self.manifest.input.height)
        input_mask = cv2.resize(
            probabilities.reshape(prototype_height, prototype_width),
            input_size,
            interpolation=cv2.INTER_LINEAR,
        )
        cropped_mask = self.crop_mask(input_mask, request.box)
        frame_height, frame_width = request.frame_shape
        frame_mask = cv2.resize(
            cropped_mask,
            (frame_width, frame_height),
            interpolation=cv2.INTER_LINEAR,
        )
        binary_mask = np.asarray(
            frame_mask >= self.mask_threshold,
            dtype=np.uint8,
        )
        return SegmentationMaskModel(
            polygons=self.mask_polygons(binary_mask)
        )

    def crop_mask(
        self,
        mask: NDArray[np.floating],
        box: NDArray[np.float32],
    ) -> NDArray[np.floating]:
        left, top, width, height = box
        input_width = self.manifest.input.width
        input_height = self.manifest.input.height
        xmin = int(np.clip(np.floor(left), 0, input_width))
        ymin = int(np.clip(np.floor(top), 0, input_height))
        xmax = int(np.clip(np.ceil(left + width), 0, input_width))
        ymax = int(np.clip(np.ceil(top + height), 0, input_height))
        cropped = np.zeros_like(mask)
        if xmin < xmax and ymin < ymax:
            cropped[ymin:ymax, xmin:xmax] = mask[ymin:ymax, xmin:xmax]
        return cropped

    @staticmethod
    def mask_polygons(mask: NDArray[np.uint8]) -> list[list[NormalizedPoint]]:
        contours, _ = cv2.findContours(
            mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        height, width = mask.shape
        x_denominator = max(width - 1, 1)
        y_denominator = max(height - 1, 1)
        polygons: list[list[NormalizedPoint]] = []
        for contour in contours:
            if len(contour) < 3:
                continue
            polygon = [
                NormalizedPoint(
                    x=float(point[0][0] / x_denominator),
                    y=float(point[0][1] / y_denominator),
                )
                for point in contour
            ]
            polygons.append(polygon)
        return polygons


@dataclass
class Yolov5SegModelAdapter(ObjectSegmentationAdapter):
    provider: ClassVar[ObjectSegmentationModelProviderEnum] = (
        ObjectSegmentationModelProviderEnum.YOLOV5_SEG
    )
    class_score_offset: ClassVar[int] = 5

    def prepare_prediction_rows(
        self,
        predictions: NDArray[np.generic],
    ) -> NDArray[np.float32]:
        if predictions.ndim != 3 or predictions.shape[0] != 1:
            raise ValueError(
                "YOLOv5 segmentation predictions must have shape "
                f"(1, predictions, values); received {predictions.shape}"
            )
        if not np.issubdtype(predictions.dtype, np.floating):
            raise ValueError("YOLOv5 segmentation predictions must be floating point")
        return np.asarray(predictions[0], dtype=np.float32)

    def confidence_scores(
        self,
        rows: NDArray[np.float32],
        class_scores: NDArray[np.float32],
        class_ids: NDArray[np.integer],
    ) -> NDArray[np.float32]:
        selected_scores = class_scores[np.arange(len(rows)), class_ids]
        return np.asarray(rows[:, 4] * selected_scores, dtype=np.float32)


@dataclass
class Yolov8SegModelAdapter(ObjectSegmentationAdapter):
    provider: ClassVar[ObjectSegmentationModelProviderEnum] = (
        ObjectSegmentationModelProviderEnum.YOLOV8_SEG
    )
    class_score_offset: ClassVar[int] = 4

    def prepare_prediction_rows(
        self,
        predictions: NDArray[np.generic],
    ) -> NDArray[np.float32]:
        if predictions.ndim != 3 or predictions.shape[0] != 1:
            raise ValueError(
                "YOLOv8 segmentation predictions must have shape "
                f"(1, values, predictions); received {predictions.shape}"
            )
        if not np.issubdtype(predictions.dtype, np.floating):
            raise ValueError("YOLOv8 segmentation predictions must be floating point")
        return np.asarray(predictions[0].T, dtype=np.float32)

    def confidence_scores(
        self,
        rows: NDArray[np.float32],
        class_scores: NDArray[np.float32],
        class_ids: NDArray[np.integer],
    ) -> NDArray[np.float32]:
        return np.asarray(
            class_scores[np.arange(len(rows)), class_ids],
            dtype=np.float32,
        )


OBJECT_SEGMENTATION_MODEL_REGISTRY: dict[
    ObjectSegmentationModelProviderEnum,
    type[ObjectSegmentationAdapter],
] = {
    ObjectSegmentationModelProviderEnum.YOLOV5_SEG: Yolov5SegModelAdapter,
    ObjectSegmentationModelProviderEnum.YOLOV8_SEG: Yolov8SegModelAdapter,
}
