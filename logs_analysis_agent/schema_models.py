import logging
from typing import Any, Dict, List, Mapping, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class IdentificationRule(BaseModel):
    """Rule for identifying a specific log type."""
    field: str = Field(..., description="Field name in the raw event to evaluate.")
    operator: str = Field(
        ..., description="Comparison operator (e.g., equals, contains, etc.)."
    )
    value: Any = Field(
        ..., description="Value to compare against; may be string, number, or pattern."
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Heuristic confidence [0.0, 1.0] for this rule."
    )


class IdentificationRules(BaseModel):
    """Collection of identification rules for a log type."""
    primary: List[IdentificationRule] = Field(
        ..., description="High-signal rules that primarily identify this log type."
    )
    secondary: List[IdentificationRule] = Field(
        default_factory=list,
        description="Supplementary rules that may strengthen identification.",
    )


class ParsedFieldMetadata(BaseModel):
    """Metadata about a parsing operation performed on a field."""
    field_path: str = Field(
        ...,
        description="The field path that was parsed (from raw data or within a parent's parsed result)."
    )
    parsers_or_formats: List[str] = Field(
        ...,
        description="Ordered list of parsers/formats applied to this field (e.g., ['base64-decode', 'json_parser'])."
    )
    resulting_field_paths: List[str] = Field(
        default_factory=list,
        description="Immediate field paths created by parsing this field (not including nested descendants)."
    )
    parent_parsed_field: Optional[str] = Field(
        default=None,
        description="If this field was parsed from within another parsed field, the parent field path. None for top-level parsed fields."
    )
    parse_level: int = Field(
        default=0,
        description="Depth of parsing: 0 for fields parsed from raw data, 1 for fields parsed from level-0 results, etc."
    )


class FieldSchema(BaseModel):
    """Schema definition for a single field in a log type."""
    field_path: str = Field(
        ..., description="Dot-path to the field in the event (e.g., location.ipAddress)."
    )
    semantic_type: str = Field(
        ..., description="Meaningful category of the field (e.g., ip_address, timestamp)."
    )
    examples: List[Any] = Field(
        default_factory=list, description="Representative example values from the actual data."
    )
    common_patterns: List[str] = Field(
        default_factory=list,
        description="Common formatting/pattern hints for parsing and validation.",
    )


class LogType(BaseModel):
    """Complete definition of a discovered log type."""
    name: str = Field(..., description="Human-readable name for the log type.")
    primary_use: str = Field(
        ..., description="Primary analytics purpose of this log type (what insights it enables)."
    )
    count_in_dataset: int = Field(
        ..., ge=0, description="Observed count of events for this type in the dataset."
    )
    identification_rules: IdentificationRules = Field(
        ..., description="Rules used to identify events belonging to this log type."
    )
    schema: Mapping[str, FieldSchema] = Field(
        ..., description="Field name to schema mapping describing structure and semantics."
    )
    parsing_metadata: List[ParsedFieldMetadata] = Field(
        default_factory=list,
        description="Hierarchical metadata about all parsing operations performed on this log type. Empty list if no parsing was needed."
    )


class SchemaDocument(BaseModel):
    """
    Complete schema analysis document for a log index.
    
    This is the main output of the log analysis agent, containing all
    discovered log types, their schemas, and analysis metadata.
    """
    index_name: str
    total_logs_analyzed: int = Field(
        ..., ge=0, description="Total number of log events processed in this analysis run."
    )
    analysis_batches_processed: int = Field(
        ..., ge=0, description="Number of batches/windows analyzed to produce this summary."
    )
    log_types: Dict[str, LogType] = Field(
        ..., description="Mapping of internal keys to log type definitions and schemas."
    )
    analysis_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Overall confidence [0.0, 1.0] in the analysis results."
    )
    stopping_reason: str = Field(
        ..., description="Why analysis stopped (e.g., no-new-fields, time-limit, quality-threshold)."
    )
    data_quality_issues: List[str] = Field(
        default_factory=list,
        description="Notable data issues encountered (e.g., malformed fields, missing values).",
    )
    requires_human_review: bool = Field(
        ..., description="Whether a human should review results due to uncertainty or issues."
    )
    analysis_notes: str = Field(
        ..., description="Free-form notes with context, caveats, and next steps for analysts."
    )
    processing_time_minutes: float = Field(
        ..., ge=0.0, description="Wall-clock processing time for the analysis, in minutes."
    )

