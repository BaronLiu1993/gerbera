from gerbera_harness.runtime.schemas.base import HarnessSchema


class PhysicalConfigurationStateSchema(HarnessSchema):
    session_id: str
    # keyed by the movement system and the entire object
    movement_system_configuration: dict[str, object]
