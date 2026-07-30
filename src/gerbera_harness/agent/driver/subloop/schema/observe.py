from typing import Any

from gerbera_harness.agent.driver.subloop.schema.base import StrictSchema


class ObserveSchema(StrictSchema):
    activated_cameras: list[str]
    activated_sensors: list[str]
    hardware_state: dict[str, Any]
