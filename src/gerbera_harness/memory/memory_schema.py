import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import Field

from gerbera_harness.domain.schema import StrictSchema
from gerbera_harness.domain.experiment import (
    ExecuteActionGroupSchema,
)
from gerbera_harness.domain.experiment import (
    HypothesisSchema,
)

class EventTypeEnum(str, Enum):
    SENSOR_READING = "sensor_reading"
    WORLD_STATE_UPDATED = "world_state_updated"

    SKILL_STARTED = "skill_started"
    SKILL_PROGRESS = "skill_progress"
    SKILL_COMPLETED = "skill_completed"
    SKILL_FAILED = "skill_failed"
    SKILL_RETRYING = "skill_retrying"

    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"

    PLAN_CREATED = "plan_created"
    PLAN_INVALIDATED = "plan_invalidated"
    REPLAN_REQUESTED = "replan_requested"

    # SAFETY_STOP = "safety_stop"
    # SAFETY_BLOCKED = "safety_blocked"

    TOOL_CALL = "tool_call"
    USER_COMMAND = "user_command"


class EventSchema(StrictSchema):
    session_id: str
    event_type: EventTypeEnum
    source_name: str
    payload: dict[str, Any]
    task_id: str | None = None
    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

class EventStateSchema(StrictSchema):
    session_id: str
    events: list[EventSchema] = Field(default_factory=list)

# Hardware State
class HardwareComponentEnum(str, Enum):
    SERVO_MOTOR = "servo_motor"
    DC_MOTOR = "dc_motor"
    IR_SENSOR = "ir_sensor"


class HardwareEdgeSchema(StrictSchema):
    source_id: str
    target_id: str
    description: str
    relationship_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class HardwareNodeSchema(StrictSchema):
    component_name: str
    description: str
    component_type: HardwareComponentEnum
    capabilities: dict[str, Any]
    hardware_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class HardwareConfigurationStateSchema(StrictSchema):
    session_id: str
    description: str
    hardware_nodes: list[HardwareNodeSchema] = Field(default_factory=list)
    hardware_edges: list[HardwareEdgeSchema] = Field(default_factory=list)



# World state, answers what is currently in the frame?
class WorldStateSchema(StrictSchema):
    session_id: str
    environment_state: dict[str, Any] = Field(default_factory=dict)
    hardware_state: dict[str, Any] = Field(default_factory=dict)
    sources: list[str] = Field(default_factory=list)
    world_state_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    observed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# Tools, Answer what are the low level details that were ran
class ToolStatusEnum(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


class ToolSchema(StrictSchema):
    session_id: str
    tool_name: str
    tool_status: ToolStatusEnum
    result: dict[str, Any] = Field(default_factory=dict)

    error_code: str | None = None
    error_message: str | None = None
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    tool_call_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


# Tasks
class TaskStatusEnum(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


# What are the high level details of a task, a task contains many tools
class TaskSchema(StrictSchema):
    task_goal: str
    status: TaskStatusEnum
    task: ExecuteActionGroupSchema

    session_id: str
    attempts: int = 0
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tool_calls: list[ToolSchema] = Field(default_factory=list)
    result: dict[str, Any] | None = None
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    finished_at: datetime | None = None


class TaskStateSchema(StrictSchema):
    hypothesis: HypothesisSchema | None = None
    tasks: list[TaskSchema] = Field(default_factory=list)
    current_task_id: str | None = None


class TemporalStateSchema(StrictSchema):
    session_id: str
    current_hardware_configuration: dict[str, Any] # the servo, with the value of what it is right now if it is staeful, for sensors stream is on for instance
    recent_world_states: list[WorldStateSchema] = Field(default_factory=list)
    recent_tool_results: list[ToolSchema] = Field(default_factory=list)
    recent_task_results: list[TaskSchema] = Field(default_factory=list)
    temporal_memory_id: str = Field(default_factory=lambda: str(uuid.uuid4()))




