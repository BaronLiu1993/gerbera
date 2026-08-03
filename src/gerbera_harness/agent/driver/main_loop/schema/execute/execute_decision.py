from enum import Enum


class ExecuteDecisionEnum(str, Enum):
    ACCEPTED = "accepted"
    FAILED = "failed"
