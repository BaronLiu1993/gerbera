from enum import StrEnum
from typing import Any

from mcp.types import Tool


TOOL_STAGES_META_KEY = "gerbera.dev/tool-stages"


class ToolStage(StrEnum):
    OBSERVATION = "observation"


def stage_metadata(*stages: ToolStage) -> dict[str, Any]:
    return {TOOL_STAGES_META_KEY: [stage.value for stage in stages]}


def tool_is_available_during(tool: Tool, stage: ToolStage) -> bool:
    annotations = tool.annotations
    if stage is ToolStage.OBSERVATION and (
        annotations is not None and annotations.readOnlyHint is True
    ):
        return True

    metadata = tool.meta or {}
    configured_stages = metadata.get(TOOL_STAGES_META_KEY, [])
    return (
        isinstance(configured_stages, list)
        and stage.value in configured_stages
    )
