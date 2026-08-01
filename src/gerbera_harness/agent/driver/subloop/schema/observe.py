from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from gerbera_harness.agent.driver.subloop.schema.base import StrictSchema


class ObservationSourceTypeEnum(str, Enum):
    SENSOR = "sensor"
    CAMERA = "camera"


class SensorReadingSchema(StrictSchema):
    name: str
    value: bool | int | float | str
    unit: str | None = None


class SensorObservationSchema(StrictSchema):
    type: Literal[ObservationSourceTypeEnum.SENSOR]
    event_id: str
    source_name: str
    microcontroller_id: str
    event_name: str
    observed_at: datetime
    readings: list[SensorReadingSchema]
    stale: bool


class VisionObservationSchema(StrictSchema):
    environment_name: str
    description: str
    objects: list[dict[str, object]]


class CameraObservationSchema(StrictSchema):
    type: Literal[ObservationSourceTypeEnum.CAMERA]
    event_id: str
    source_name: str
    observed_at: datetime
    frame_id: str
    vision: VisionObservationSchema
    stale: bool


ObservationSchema = Annotated[
    SensorObservationSchema | CameraObservationSchema,
    Field(discriminator="type"),
]


class ObservationErrorSchema(StrictSchema):
    source_name: str | None = None
    message: str
    observed_at: datetime


class ObserveSchema(StrictSchema):
    space_name: str
    observed_from: datetime
    observed_until: datetime
    read_only: Literal[True] = True
    observations: list[ObservationSchema]
    complete: bool
    errors: list[ObservationErrorSchema]

    @model_validator(mode="after")
    def validate_time_window(self) -> "ObserveSchema":
        if self.observed_from > self.observed_until:
            raise ValueError(
                "observed_from must be before or equal to observed_until"
            )
        return self
