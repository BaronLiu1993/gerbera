import json
from dataclasses import dataclass
from datetime import datetime, timezone

from gerbera_harness.runtime.execute_producer.schemas import (
    JsonScalar,
    ObservationResponseSchema,
    ObservationResultSchema,
    ObservationReviewSchema,
    ObservationStatusEnum,
    ObservationToolCallSchema,
    ObservationValueSchema,
    observation_adapter,
    observation_review_adapter,
)
from gerbera_harness.infrastructure.mcp import MCPClient
from gerbera_harness.infrastructure.model import Model
# from gerbera_harness.runtime.execute_producer.context import (
#     ObservationPromptContextBuilder,
# )
from gerbera_harness.memory.schemas.world import WorldStateSchema
from gerbera_harness.prompts import PromptTypeEnum, load_prompt
from gerbera_harness.tools.registry import LocalToolRegistry

OBSERVATION_PROMPT = load_prompt(PromptTypeEnum.SUB, "OBSERVE.md")
OBSERVATION_REVIEW_PROMPT = load_prompt(
    PromptTypeEnum.SUB,
    "OBSERVATION_REVIEW.md",
)


@dataclass
class ObservationRuntime:
    model: Model
    mcp_url: str
    context_builder: ObservationPromptContextBuilder
    local_tool_registry: LocalToolRegistry