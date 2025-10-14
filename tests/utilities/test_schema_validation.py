import pytest
import json
from langchain_core.tools import ToolException

from utilities.tools.schema_validation import parse_and_validate_schema_document
from models.log_type_schema import SchemaDocument


class TestParseAndValidateSchemaDocument:
    """Test suite for parse_and_validate_schema_document tool."""

    def test_parse_valid_minimal_schema(self):
        """Test parsing a minimal valid SchemaDocument."""
        minimal_json = json.dumps({
            "index_name": "minimal",
            "total_logs_analyzed": 0,
            "analysis_batches_processed": 0,
            "log_types": {},
            "analysis_confidence": 1.0,
            "stopping_reason": "no-data",
            "requires_human_review": False,
            "analysis_notes": "No logs found",
            "processing_time_minutes": 0.1
        })
        
        result = parse_and_validate_schema_document.func(minimal_json)
        assert isinstance(result, SchemaDocument)
        assert result.index_name == "minimal"
        assert len(result.log_types) == 0

    @pytest.mark.parametrize(
        "invalid_input,error_pattern",
        [
            pytest.param('{"invalid": json}', "not valid JSON", id="invalid_json_syntax"),
            pytest.param('', "not valid JSON", id="empty_string"),
            pytest.param("{'key': 'value'}", "not valid JSON", id="single_quotes_json"),
            pytest.param('[{"field": "value"}]', "valid dictionary", id="json_array_not_object"),
            pytest.param('{"wrong_field": "value"}', "SchemaDocument validation", id="wrong_fields_only"),
            pytest.param('{"index_name": "test"}', "SchemaDocument validation", id="missing_required_fields"),
        ]
    )
    def test_parse_error_cases(self, invalid_input, error_pattern):
        """Test errors when parsing invalid input."""
        with pytest.raises(ToolException, match=error_pattern):
            parse_and_validate_schema_document.func(invalid_input)

    @pytest.mark.parametrize(
        "missing_field",
        [
            pytest.param("total_logs_analyzed", id="missing_total_logs_analyzed"),
            pytest.param("analysis_batches_processed", id="missing_analysis_batches_processed"),
            pytest.param("log_types", id="missing_log_types"),
            pytest.param("analysis_confidence", id="missing_analysis_confidence"),
            pytest.param("stopping_reason", id="missing_stopping_reason"),
            pytest.param("requires_human_review", id="missing_requires_human_review"),
            pytest.param("analysis_notes", id="missing_analysis_notes"),
            pytest.param("processing_time_minutes", id="missing_processing_time_minutes"),
        ]
    )
    def test_parse_missing_required_field_scenarios(self, missing_field):
        """Test that each required field is validated when missing."""
        base_schema = {
            "index_name": "test_index",
            "total_logs_analyzed": 100,
            "analysis_batches_processed": 2,
            "log_types": {},
            "analysis_confidence": 0.9,
            "stopping_reason": "no-new-fields",
            "requires_human_review": False,
            "analysis_notes": "Test notes",
            "processing_time_minutes": 1.5,
            "wrong_field": "should_be_ignored"
        }
        
        # Remove the field we're testing
        del base_schema[missing_field]
        
        schema_json = json.dumps(base_schema)
        
        with pytest.raises(ToolException, match="SchemaDocument validation"):
            parse_and_validate_schema_document.func(schema_json)

    def test_parse_schema_with_simple_parsing_metadata(self):
        """Test parsing SchemaDocument with simple top-level parsing metadata."""
        schema_json = json.dumps({
            "index_name": "cef_logs_index",
            "total_logs_analyzed": 100,
            "analysis_batches_processed": 2,
            "log_types": {
                "cef_security": {
                    "name": "CEF Security Logs",
                    "primary_use": "Security event monitoring",
                    "count_in_dataset": 100,
                    "identification_rules": {
                        "primary": [
                            {
                                "field": "_raw",
                                "operator": "contains",
                                "value": "CEF:",
                                "confidence": 0.95
                            }
                        ],
                        "secondary": []
                    },
                    "schema": {
                        "message_raw.cef_header.version": {
                            "field_path": "message_raw.cef_header.version",
                            "semantic_type": "version",
                            "examples": ["0"],
                            "common_patterns": ["CEF version number"]
                        },
                        "message_raw.extension.src": {
                            "field_path": "message_raw.extension.src",
                            "semantic_type": "ip_address",
                            "examples": ["10.1.1.1", "192.168.1.1"],
                            "common_patterns": ["IPv4 address"]
                        }
                    },
                    "parsing_metadata": [
                        {
                            "field_path": "message_raw",
                            "parsers_or_formats": ["cef_parser"],
                            "resulting_field_paths": ["message_raw.cef_header", "message_raw.extension"],
                            "parent_parsed_field": None,
                            "parse_level": 0
                        }
                    ]
                }
            },
            "analysis_confidence": 0.9,
            "stopping_reason": "no-new-fields",
            "data_quality_issues": [],
            "requires_human_review": False,
            "analysis_notes": "CEF logs successfully parsed",
            "processing_time_minutes": 1.5
        })
        
        result = parse_and_validate_schema_document.func(schema_json)
        assert isinstance(result, SchemaDocument)
        assert len(result.log_types) == 1
        
        log_type = result.log_types["cef_security"]
        assert len(log_type.parsing_metadata) == 1
        
        metadata = log_type.parsing_metadata[0]
        assert metadata.field_path == "message_raw"
        assert metadata.parsers_or_formats == ["cef_parser"]
        assert metadata.resulting_field_paths == ["message_raw.cef_header", "message_raw.extension"]
        assert metadata.parent_parsed_field is None
        assert metadata.parse_level == 0

    def test_parse_schema_with_nested_parsing_metadata(self):
        """Test parsing SchemaDocument with nested/hierarchical parsing metadata."""
        schema_json = json.dumps({
            "index_name": "nested_parsing",
            "total_logs_analyzed": 50,
            "analysis_batches_processed": 1,
            "log_types": {
                "nested_logs": {
                    "name": "Logs with Nested Parsing",
                    "primary_use": "Complex nested data analysis",
                    "count_in_dataset": 50,
                    "identification_rules": {
                        "primary": [
                            {
                                "field": "type",
                                "operator": "equals",
                                "value": "nested",
                                "confidence": 0.9
                            }
                        ],
                        "secondary": []
                    },
                    "schema": {
                        "message_raw.extension.payload.user_id": {
                            "field_path": "message_raw.extension.payload.user_id",
                            "semantic_type": "user_id",
                            "examples": ["user123", "admin"],
                            "common_patterns": ["alphanumeric string"]
                        },
                        "message_raw.extension.payload.timestamp": {
                            "field_path": "message_raw.extension.payload.timestamp",
                            "semantic_type": "timestamp",
                            "examples": ["2025-01-01T10:00:00Z"],
                            "common_patterns": ["ISO 8601"]
                        }
                    },
                    "parsing_metadata": [
                        {
                            "field_path": "message_raw",
                            "parsers_or_formats": ["cef_parser"],
                            "resulting_field_paths": ["message_raw.cef_header", "message_raw.extension"],
                            "parent_parsed_field": None,
                            "parse_level": 0
                        },
                        {
                            "field_path": "message_raw.extension.payload",
                            "parsers_or_formats": ["json_parser"],
                            "resulting_field_paths": ["message_raw.extension.payload.user_id", "message_raw.extension.payload.timestamp"],
                            "parent_parsed_field": "message_raw",
                            "parse_level": 1
                        }
                    ]
                }
            },
            "analysis_confidence": 0.85,
            "stopping_reason": "no-new-fields",
            "data_quality_issues": [],
            "requires_human_review": False,
            "analysis_notes": "Successfully parsed nested structures",
            "processing_time_minutes": 2.0
        })
        
        result = parse_and_validate_schema_document.func(schema_json)
        log_type = result.log_types["nested_logs"]
        assert len(log_type.parsing_metadata) == 2
        
        top_level = log_type.parsing_metadata[0]
        assert top_level.parse_level == 0
        assert top_level.parent_parsed_field is None
        
        nested = log_type.parsing_metadata[1]
        assert nested.field_path == "message_raw.extension.payload"
        assert nested.parent_parsed_field == "message_raw"
        assert nested.parse_level == 1

    def test_parse_schema_with_multiphase_parsing(self):
        """Test parsing SchemaDocument with multi-phase parsing (multiple parsers on one field)."""
        schema_json = json.dumps({
            "index_name": "multiphase",
            "total_logs_analyzed": 75,
            "analysis_batches_processed": 2,
            "log_types": {
                "encoded_logs": {
                    "name": "Base64 Encoded JSON Logs",
                    "primary_use": "Encoded message analysis",
                    "count_in_dataset": 75,
                    "identification_rules": {
                        "primary": [
                            {
                                "field": "encoded_data",
                                "operator": "contains",
                                "value": "eyJ",
                                "confidence": 0.8
                            }
                        ],
                        "secondary": []
                    },
                    "schema": {
                        "encoded_data.message": {
                            "field_path": "encoded_data.message",
                            "semantic_type": "message_text",
                            "examples": ["Hello world", "Test message"],
                            "common_patterns": ["Plain text"]
                        },
                        "encoded_data.user": {
                            "field_path": "encoded_data.user",
                            "semantic_type": "username",
                            "examples": ["alice", "bob"],
                            "common_patterns": ["lowercase alphanumeric"]
                        }
                    },
                    "parsing_metadata": [
                        {
                            "field_path": "encoded_data",
                            "parsers_or_formats": ["base64-decode", "json_parser"],
                            "resulting_field_paths": ["encoded_data.message", "encoded_data.user"],
                            "parent_parsed_field": None,
                            "parse_level": 0
                        }
                    ]
                }
            },
            "analysis_confidence": 0.88,
            "stopping_reason": "no-new-fields",
            "data_quality_issues": ["Some records had malformed base64"],
            "requires_human_review": False,
            "analysis_notes": "Multi-phase parsing successful",
            "processing_time_minutes": 1.2
        })
        
        result = parse_and_validate_schema_document.func(schema_json)
        log_type = result.log_types["encoded_logs"]
        assert len(log_type.parsing_metadata) == 1
        
        metadata = log_type.parsing_metadata[0]
        assert len(metadata.parsers_or_formats) == 2
        assert metadata.parsers_or_formats == ["base64-decode", "json_parser"]
        assert metadata.parse_level == 0

    def test_parse_schema_without_parsing_metadata(self):
        """Test SchemaDocument with empty parsing_metadata (backward compatibility)."""
        schema_json = json.dumps({
            "index_name": "simple_logs",
            "total_logs_analyzed": 200,
            "analysis_batches_processed": 4,
            "log_types": {
                "simple_json": {
                    "name": "Simple JSON Logs",
                    "primary_use": "Basic log analysis",
                    "count_in_dataset": 200,
                    "identification_rules": {
                        "primary": [
                            {
                                "field": "log_type",
                                "operator": "equals",
                                "value": "simple",
                                "confidence": 1.0
                            }
                        ],
                        "secondary": []
                    },
                    "schema": {
                        "timestamp": {
                            "field_path": "timestamp",
                            "semantic_type": "timestamp",
                            "examples": ["2025-01-01T00:00:00Z"],
                            "common_patterns": ["ISO 8601"]
                        },
                        "user_id": {
                            "field_path": "user_id",
                            "semantic_type": "user_id",
                            "examples": ["12345"],
                            "common_patterns": ["numeric string"]
                        }
                    },
                    "parsing_metadata": []
                }
            },
            "analysis_confidence": 0.95,
            "stopping_reason": "no-new-fields",
            "data_quality_issues": [],
            "requires_human_review": False,
            "analysis_notes": "No parsing needed, logs are already structured",
            "processing_time_minutes": 0.8
        })
        
        result = parse_and_validate_schema_document.func(schema_json)
        log_type = result.log_types["simple_json"]
        assert log_type.parsing_metadata == []
        assert len(log_type.schema) == 2

