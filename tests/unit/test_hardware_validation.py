from types import SimpleNamespace

import pytest

from gerbera_sdk.inference import (
    ObjectDetectionModel,
    ObjectDetectionModelProviderEnum,
)
from gerbera_sdk.models.hardware.camera import Camera, DeviceCameraSource
from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.movement_system import (
    FixedJoint,
    Link,
    MovementSystem,
    RevoluteJoint,
)
from gerbera_sdk.models.hardware.validation import HardwareValidationFacade


def make_camera(camera_id: str = "camera-1") -> Camera:
    return Camera(
        camera_id=camera_id,
        name="camera",
        description="Test camera",
        source=DeviceCameraSource(device_index=0),
    )


def make_fixed_joint(
    name: str,
    parent: Link,
    child: Link,
) -> FixedJoint:
    return FixedJoint(
        name,
        parent,
        child,
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0),
    )


def test_facade_accepts_a_valid_complete_hardware_graph() -> None:
    motor = Connection(
        name="shoulder-motor",
        component_type="sg90",
        pins={"signal": "9"},
        description="Shoulder motor",
        microcontroller_id="board-1",
    )
    board = SimpleNamespace(
        id="board-1",
        name="board",
        hardware_system_id="system-1",
        connections=[motor],
    )
    base = Link("base")
    arm = Link("arm")
    movement = MovementSystem(
        name="arm",
        base_link=base,
        joints=[
            RevoluteJoint(
                "shoulder",
                base,
                arm,
                (0.0, 0.0, 0.0),
                (0.0, 0.0, 0.0),
                axis="z",
                lower_rad=-1.0,
                upper_rad=1.0,
                motor_connection=motor,
            )
        ],
    )
    camera = make_camera()
    model = ObjectDetectionModel(
        model_name=ObjectDetectionModelProviderEnum.YOLOV5,
        name="detector",
        model_source="detector.onnx",
        subscribed_camera=camera,
    )
    system = HardwareSystem(
        id="system-1",
        name="robot",
        microcontrollers=[board],
        cameras=[camera],
        models=[model],
        movement_systems=[movement],
    )

    result = HardwareValidationFacade.validate(system)

    assert result.is_valid
    assert result.errors == ()
    result.raise_for_errors()


def test_facade_aggregates_independent_errors_and_hard_fails() -> None:
    system = HardwareSystem(
        name="",
        cameras=[make_camera("duplicate"), make_camera("duplicate")],
        movement_systems=[MovementSystem(name="", base_link=Link(""))],
    )

    result = HardwareValidationFacade.validate(system)

    assert result.errors == (
        "hardware_system.name: cannot be empty",
        "cameras[duplicate].camera_id: duplicate ID: duplicate",
        "movement_systems[<empty>].name: cannot be empty",
        "movement_systems[<empty>].base_link.name: cannot be empty",
    )
    with pytest.raises(ValueError, match="Hardware system validation failed"):
        result.raise_for_errors()


def test_model_must_reference_a_registered_camera() -> None:
    model = ObjectDetectionModel(
        model_name=ObjectDetectionModelProviderEnum.YOLOV5,
        name="detector",
        model_source="detector.onnx",
        subscribed_camera=make_camera("missing"),
    )

    result = HardwareValidationFacade.validate(
        HardwareSystem(name="robot", models=[model])
    )

    assert result.errors == (
        f"models[{model.model_id}].subscribed_camera: "
        "camera is not registered: missing",
    )


def test_movement_cycle_and_unreachable_links_are_reported() -> None:
    base = Link("base")
    first = Link("first")
    second = Link("second")
    movement = MovementSystem(
        name="arm",
        base_link=base,
        joints=[
            make_fixed_joint("first-to-second", first, second),
            make_fixed_joint("second-to-first", second, first),
        ],
    )

    result = HardwareValidationFacade.validate(
        HardwareSystem(name="robot", movement_systems=[movement])
    )

    assert "movement_systems[arm]: contains a cycle" in result.errors
    assert (
        "movement_systems[arm]: links are not reachable from base link: "
        "first, second"
    ) in result.errors


@pytest.mark.parametrize(
    ("axis", "lower", "upper", "expected_error"),
    [
        ("invalid", -1.0, 1.0, ".axis: must be one of x, y, or z: invalid"),
        ("z", 2.0, 1.0, ".limits: lower_rad cannot exceed upper_rad"),
    ],
)
def test_revolute_joint_boundaries_are_validated(
    axis: str,
    lower: float,
    upper: float,
    expected_error: str,
) -> None:
    motor = Connection(
        name="motor",
        component_type="sg90",
        pins={"signal": "9"},
        description="Motor",
    )
    base = Link("base")
    joint = RevoluteJoint(
        "shoulder",
        base,
        Link("arm"),
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0),
        axis=axis,
        lower_rad=lower,
        upper_rad=upper,
        motor_connection=motor,
    )

    result = HardwareValidationFacade.validate(
        HardwareSystem(
            name="robot",
            movement_systems=[MovementSystem("arm", base, [joint])],
        )
    )

    assert any(error.endswith(expected_error) for error in result.errors)


def test_motor_must_use_the_registered_connection_instance() -> None:
    registered_motor = Connection(
        name="motor",
        component_type="sg90",
        pins={"signal": "9"},
        description="Registered motor",
        microcontroller_id="board-1",
    )
    copied_motor = Connection(
        name="motor",
        component_type="sg90",
        pins={"signal": "9"},
        description="Copied motor",
        microcontroller_id="board-1",
    )
    board = SimpleNamespace(
        id="board-1",
        name="board",
        hardware_system_id="system-1",
        connections=[registered_motor],
    )
    base = Link("base")
    joint = RevoluteJoint(
        "shoulder",
        base,
        Link("arm"),
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0),
        axis="z",
        lower_rad=-1.0,
        upper_rad=1.0,
        motor_connection=copied_motor,
    )

    result = HardwareValidationFacade.validate(
        HardwareSystem(
            id="system-1",
            name="robot",
            microcontrollers=[board],
            movement_systems=[MovementSystem("arm", base, [joint])],
        )
    )

    assert result.errors == (
        "movement_systems[arm].joints[shoulder].motor_connection: "
        "must reference the registered connection object: motor",
    )
