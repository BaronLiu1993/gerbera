from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar, Literal, TypeAlias

from pydantic import Field, TypeAdapter

from gerbera_harness.domain.experiment import (
    ContinuousExecuteSchema,
    DiscreteExecuteSchema,
)
from gerbera_harness.domain.schema import StrictSchema


class ExecuteLoopStateEnum(str, Enum):
    OBSERVE = "observe"
    PLAN = "plan"
    ACT = "act"


@dataclass(frozen=True)
class ExecuteLoopState:
    state: ClassVar[ExecuteLoopStateEnum]
    valid_transition_states: ClassVar[frozenset[ExecuteLoopStateEnum]]

    def valid_transition(self, new_state: ExecuteLoopStateEnum) -> bool:
        return new_state in self.valid_transition_states


@dataclass(frozen=True)
class ObserveState(ExecuteLoopState):
    state: ClassVar[ExecuteLoopStateEnum] = ExecuteLoopStateEnum.OBSERVE
    valid_transition_states: ClassVar[frozenset[ExecuteLoopStateEnum]] = (
        frozenset({ExecuteLoopStateEnum.PLAN})
    )


@dataclass(frozen=True)
class PlanState(ExecuteLoopState):
    state: ClassVar[ExecuteLoopStateEnum] = ExecuteLoopStateEnum.PLAN
    valid_transition_states: ClassVar[frozenset[ExecuteLoopStateEnum]] = (
        frozenset({ExecuteLoopStateEnum.ACT, ExecuteLoopStateEnum.OBSERVE})
    )


@dataclass(frozen=True)
class ActState(ExecuteLoopState):
    state: ClassVar[ExecuteLoopStateEnum] = ExecuteLoopStateEnum.ACT
    valid_transition_states: ClassVar[frozenset[ExecuteLoopStateEnum]] = (
        frozenset({ExecuteLoopStateEnum.OBSERVE})
    )


ADAPTIVE_STATE_TYPES: dict[ExecuteLoopStateEnum, type[ExecuteLoopState]] = {
    ExecuteLoopStateEnum.OBSERVE: ObserveState,
    ExecuteLoopStateEnum.PLAN: PlanState,
    ExecuteLoopStateEnum.ACT: ActState,
}


@dataclass
class Session:
    state: ExecuteLoopState = field(default_factory=ObserveState)

    def perform_transition(
        self,
        target_state: ExecuteLoopStateEnum,
    ) -> ExecuteLoopState:
        if not self.valid_transition(target_state):
            raise ValueError("Invalid transition state")

        self.state = ADAPTIVE_STATE_TYPES[target_state]()
        return self.state

    def valid_transition(self, new_state: ExecuteLoopStateEnum) -> bool:
        target_state = ExecuteLoopStateEnum(new_state)
        return self.state.valid_transition(target_state)


class ToolCallStatusEnum(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


class ToolCallTypeEnum(str, Enum):
    FORWARD = "forward"
    REVERSE = "reverse"


class ToolCallEventSchema(StrictSchema):
    tool_name: str
    arguments: dict[str, object] = Field(default_factory=dict)
    status: ToolCallStatusEnum
    call_type: ToolCallTypeEnum
    result: object | None = None
    error_message: str | None = None


JsonScalar: TypeAlias = str | int | float | bool | None


class ObservationStatusEnum(str, Enum):
    READY = "ready"
    BLOCKED = "blocked"
    CONTINUE = "continue"
    COMPLETE = "complete"


class ObservationValueSchema(StrictSchema):
    key: str
    value: JsonScalar


class ObservationToolCallSchema(StrictSchema):
    content_type: Literal["tool_call"]
    tool_name: str
    arguments: dict[str, JsonScalar]


class ObservationResultSchema(StrictSchema):
    content_type: Literal["finish"]
    reason: str
    summary: str
    result: dict[str, JsonScalar]


class ObservationResponseSchema(StrictSchema):
    content_type: Literal["tool_call", "finish"]
    tool_name: str | None
    arguments: list[ObservationValueSchema]
    reason: str | None
    summary: str | None
    result: list[ObservationValueSchema]


class ObservationReviewSchema(StrictSchema):
    status: ObservationStatusEnum
    feedback: str


observation_adapter = TypeAdapter(ObservationResponseSchema)
observation_review_adapter = TypeAdapter(ObservationReviewSchema)

PlanningExecuteActionSchema: TypeAlias = (
    ContinuousExecuteSchema | DiscreteExecuteSchema
)


class PlanningStatusEnum(str, Enum):
    READY = "ready"
    BLOCKED = "blocked"
    CONTINUE = "continue"
    COMPLETE = "complete"


class PlanningResponseSchema(StrictSchema):
    action: PlanningExecuteActionSchema


class PlanningReviewSchema(StrictSchema):
    status: PlanningStatusEnum
    feedback: str


planning_adapter = TypeAdapter(PlanningResponseSchema)
planning_review_adapter = TypeAdapter(PlanningReviewSchema)
