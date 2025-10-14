from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Literal
from pydantic import BaseModel, Field


class BaseMetrics(BaseModel):
    run_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LLMStartMetrics(BaseMetrics):
    model_name: str
    model_version: Optional[str] = None
    prompt_bytes: int


class LLMUsageMetrics(BaseMetrics):
    tokens_prompt: int
    tokens_completion: int
    total_tokens: int


class LLMEndMetrics(BaseMetrics):
    status: Literal["ok", "error"]
    duration_ms: float


class LLMErrorMetrics(BaseMetrics):
    error_type: str
    error_message: str


class ToolStartMetrics(BaseMetrics):
    tool_name: str
    input_bytes: int
    arguments_passed: Optional[Dict[str, Any]] = None


class ToolEndMetrics(BaseMetrics):
    tool_name: str
    status: Literal["ok", "error"]
    duration_ms: float
    output_bytes: int
    result_meta: Dict[str, Any] = Field(default_factory=dict)


class ToolErrorMetrics(BaseMetrics):
    tool_name: str
    error_type: str
    error_message: str


class AgentStartMetrics(BaseMetrics):
    input_keys: Dict[str, str]
    input_byte_counts: Dict[str, int] = Field(default_factory=dict)


class AgentEndMetrics(BaseMetrics):
    status: Literal["ok", "error"]
    duration_ms: float
    output_keys: List[str]
    output_sizes: Dict[str, int]


class AgentTokenSummaryMetrics(BaseMetrics):
    tokens_billable_estimate: int
    tokens_successful: int


class ParseStartMetrics(BaseMetrics):
    target_schema: str
    schema_version: Optional[str] = None


class ParseEndMetrics(BaseMetrics):
    target_schema: str
    status: Literal["ok", "error"]
    duration_ms: float
    parsed_bytes: int


class ParseValidationMetrics(BaseMetrics):
    target_schema: str
    errors_count: int
    top_n_field_errors: List[Dict[str, str]] = Field(default_factory=list)
    error_rate: float = Field(ge=0.0, le=1.0)


class BatchStartMetrics(BaseMetrics):
    batch_number: int
    lines_to_read: int


class BatchEndMetrics(BaseMetrics):
    batch_number: int
    lines_read: int
    cumulative_lines_processed: int
    duration_ms: float


class BatchDiscoveryMetrics(BaseMetrics):
    batch_number: int
    new_log_types_found: int
    new_fields_found: int


class HandleOpenMetrics(BaseMetrics):
    handle_id: str
    file_path: str
    total_lines: Optional[int] = None


class HandleCloseMetrics(BaseMetrics):
    handle_id: str
    total_lines_read: int
    duration_open_ms: float


class AgentIterationMetrics(BaseMetrics):
    iteration_number: int
    action_type: str
    action_input_summary: str
    observation_summary: str

