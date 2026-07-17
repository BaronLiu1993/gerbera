from dataclasses import dataclass, field
import uuid
from enum import Enum

from method import Method


class HypothesisStateEnum(Enum):
    DRAFT = "draft"
    EVALUATING = "evaluating"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class HypothesisTypeEnum(Enum):
    NULL = "null"
    ALTERNATIVE = "alternative"


@dataclass
class Hypothesis:
    statement: str
    state: HypothesisStateEnum
    dependent_variables: list[str]
    independent_variables: list[str]
    assumptions: list[str]
    hypothesis_type: HypothesisTypeEnum
    methods: list[Method]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
