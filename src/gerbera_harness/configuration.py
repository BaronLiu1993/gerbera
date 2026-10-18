from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator

from gerbera_harness.models.settings import TokenLimitParameter
from gerbera_harness.runtime.state_machine.schemas import WorkflowSchema


class ModelSettings(WorkflowSchema):
    type: Literal["api", "local"] = "api"
    provider: str = "openai"
    name: str = Field(min_length=1)
    endpoint: str | None = None
    api_key_env: str = "API_KEY"
    maximum_tokens: int = Field(default=8192, ge=1)
    timeout_seconds: float = Field(default=120, gt=0, allow_inf_nan=False)
    token_limit_parameter: TokenLimitParameter | None = None


class ConnectorSettings(WorkflowSchema):
    mcp_url: str
    physical_state: bool = True

    @field_validator("mcp_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("The SDK connector requires an HTTP or HTTPS URL")
        return value


class HarnessSettings(WorkflowSchema):
    schema_version: Literal["1"] = "1"
    model: ModelSettings
    connector: ConnectorSettings | None = None
    default_workflow: str = "simple"
    workflows: dict[str, str] = Field(default_factory=dict)
    extensions: tuple[Literal["database", "sandbox", "event_recording"], ...] = (
        "event_recording",
    )
