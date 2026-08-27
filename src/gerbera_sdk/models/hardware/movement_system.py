from dataclasses import dataclass, field
from typing import Literal
from gerbera_sdk.models.hardware.connection import Connection

Axis = Literal["x", "y", "z"]

@dataclass
class Link:
    name: str
    description: str = ""


@dataclass
class BaseJoint:
    joint_name: str

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
    description: str = ""


@dataclass
class RevoluteJoint(BaseJoint):
    axis: Axis
    lower_rad: float
    upper_rad: float
    motor_connection: Connection  # match with the motor name 


@dataclass
class PrismaticJoint(BaseJoint):
    axis: Axis
    lower_m: float
    upper_m: float
    motor_connection: Connection  # match with the motor


@dataclass
class ContinuousJoint(BaseJoint):
    axis: Axis
    motor_connection: Connection  # match with the motor


@dataclass
class FixedJoint(BaseJoint):
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


@dataclass
class MovementSystem:
    base_link: Link
    joints: list[Joint] = field(default_factory=list)