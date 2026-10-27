import pytest

from gerbera_sdk.inference import (
    ObjectDetectionModel,
)
from gerbera_sdk.models.hardware.camera import Camera, DeviceCameraSource
from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import (
    RuntimeTransportConfig,
    Microcontroller,
    RuntimeWatchdogConfig,
)
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
        name="shoulder_motor",
        component_type="sg90",
        pins={"signal": "9"},
        description="Shoulder motor",
        microcontroller_id="board-1",
    )
    board = Microcontroller(
        runtime_transport=RuntimeTransportConfig.usb_serial("/dev/board-1"),
        device_id="board-1",
        name="board",
        upload_port="/dev/board-1",
        fqbn="arduino:avr:uno",
        watchdog=RuntimeWatchdogConfig(
            heartbeat_interval_ms=100,
            heartbeat_timeout_ms=500,
        ),
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
        name="detector",
        model_directory="detector",
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


def test_facade_returns_first_error_and_hard_fails() -> None:
    system = HardwareSystem(
        name="robot",
        cameras=[make_camera("duplicate"), make_camera("duplicate")],
        movement_systems=[MovementSystem(name="arm", base_link=Link("base"))] * 2,
    )

    result = HardwareValidationFacade.validate(system)

    assert result.errors == (
        "cameras[duplicate].camera_id: duplicate ID: duplicate",
    )
    with pytest.raises(ValueError, match="Hardware system validation failed"):
        result.raise_for_errors()


def test_model_must_reference_a_registered_camera() -> None:
    model = ObjectDetectionModel(
        name="detector",
        model_directory="detector",
        subscribed_camera=make_camera("missing"),
    )

    result = HardwareValidationFacade.validate(
        HardwareSystem(name="robot", models=[model])
    )

    assert result.errors == (
        f"models[{model.model_id}].subscribed_camera: "
        "camera is not registered: missing",
    )


def test_movement_cycle_is_the_first_reported_graph_error() -> None:
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

    assert result.errors == ("movement_systems[arm]: contains a cycle",)


def test_revolute_joint_rejects_reversed_limits() -> None:
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
        axis="z",
        lower_rad=2.0,
        upper_rad=1.0,
        motor_connection=motor,
    )

    result = HardwareValidationFacade.validate(
        HardwareSystem(
            name="robot",
            movement_systems=[MovementSystem("arm", base, [joint])],
        )
    )

    assert any(error.endswith(".limits: lower_rad cannot exceed upper_rad") for error in result.errors)


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
    board = Microcontroller(
        runtime_transport=RuntimeTransportConfig.usb_serial("/dev/board-1"),
        device_id="board-1",
        name="board",
        upload_port="/dev/board-1",
        fqbn="arduino:avr:uno",
        watchdog=RuntimeWatchdogConfig(
            heartbeat_interval_ms=100,
            heartbeat_timeout_ms=500,
        ),
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


def test_joint_schema_rejects_invalid_axis_before_graph_validation() -> None:
    motor = Connection("motor", "sg90", {"signal": "9"}, "Motor")
    with pytest.raises(ValueError, match="axis"):
        RevoluteJoint(
            "shoulder", Link("base"), Link("arm"), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0),
            axis="invalid", lower_rad=-1.0, upper_rad=1.0, motor_connection=motor,
        )
