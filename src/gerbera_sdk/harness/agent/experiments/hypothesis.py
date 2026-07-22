from dataclasses import dataclass, field
import uuid
from enum import Enum

from method import Method


class HypothesisStateEnum(Enum):
    DRAFT = "draft"
    EVALUATING = "evaluating"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    


@dataclass
class Hypothesis:
    hypothesis: str # This will be the goal
    state: HypothesisStateEnum
    dependent_variables: list[str]
    independent_variables: list[str]
    controlled_variables: list[str]
    assumptions: list[str]
    methods: list[Method]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
