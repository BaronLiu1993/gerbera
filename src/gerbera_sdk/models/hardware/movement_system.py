from dataclasses import field
from typing import Annotated, Literal

from pydantic import ConfigDict, Field
from pydantic.dataclasses import dataclass
from gerbera_sdk.models.hardware.connection import Connection

Axis = Literal["x", "y", "z"]
JointType = Literal["revolute", "prismatic", "continuous", "fixed"]

@dataclass(config=ConfigDict(strict=True, extra="forbid", validate_assignment=True, validate_default=True, allow_inf_nan=False))
class Link:
    name: Annotated[str, Field(min_length=1, pattern=r"\S")]
    description: str = ""


@dataclass(config=ConfigDict(strict=True, extra="forbid", validate_assignment=True, validate_default=True, allow_inf_nan=False))
class BaseJoint:
    name: Annotated[str, Field(min_length=1, pattern=r"\S")]

    # The edge that connects it.
    parent_link: Link  # the key to the link of the parent
    child_link: Link  # the key to the link of the child

    # Where the joint is located relative to its parent link.
    # Link in meters parent_link -> joint -> child_link.
    parent_to_joint_xyz_m: tuple[float, float, float]
    parent_to_joint_rpy_rad: tuple[float, float, float]

    # Where the joint is, roll is rotation around X axis,
    # pitch is the rotation around Y axis and the yaw is the
    # rotation around Z axis.
    description: str = field(default="", kw_only=True)
    joint_type: JointType = field(init=False)


@dataclass(config=ConfigDict(strict=True, extra="forbid", validate_assignment=True, validate_default=True, allow_inf_nan=False))
class RevoluteJoint(BaseJoint):
    joint_type: Literal["revolute"] = field(default="revolute", init=False)
    axis: Axis
    lower_rad: float
    upper_rad: float
    motor_connection: Connection  # match with the motor name 


@dataclass(config=ConfigDict(strict=True, extra="forbid", validate_assignment=True, validate_default=True, allow_inf_nan=False))
class PrismaticJoint(BaseJoint):
    joint_type: Literal["prismatic"] = field(default="prismatic", init=False)
    axis: Axis
    lower_m: float
    upper_m: float
    motor_connection: Connection  # match with the motor


@dataclass(config=ConfigDict(strict=True, extra="forbid", validate_assignment=True, validate_default=True, allow_inf_nan=False))
class ContinuousJoint(BaseJoint):
    joint_type: Literal["continuous"] = field(default="continuous", init=False)
    axis: Axis
    motor_connection: Connection  # match with the motor


@dataclass(config=ConfigDict(strict=True, extra="forbid", validate_assignment=True, validate_default=True, allow_inf_nan=False))
class FixedJoint(BaseJoint):
    joint_type: Literal["fixed"] = field(default="fixed", init=False)
    # TODO: Add a sensor/camera attachment model later. A sensor should be able
    # to attach to a link with a local xyz/rpy offset so its pose moves with
    # that part of the robot.
    pass


Joint = (
    RevoluteJoint
    | PrismaticJoint
    | ContinuousJoint
    | FixedJoint
)


@dataclass(config=ConfigDict(strict=True, extra="forbid", validate_assignment=True, validate_default=True, allow_inf_nan=False))
class MovementSystem:
    name: Annotated[str, Field(min_length=1, pattern=r"\S")]
    base_link: Link
    joints: list[Joint] = field(default_factory=list)
