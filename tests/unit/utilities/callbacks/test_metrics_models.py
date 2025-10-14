import pytest
from datetime import datetime
from pydantic import ValidationError

from utilities.callbacks.metrics_models import (
    BaseMetrics,
    LLMStartMetrics,
    LLMUsageMetrics,
    LLMEndMetrics,
    LLMErrorMetrics,
    ToolStartMetrics,
    ToolEndMetrics,
    ToolErrorMetrics,
    AgentStartMetrics,
    AgentEndMetrics,
    AgentTokenSummaryMetrics,
    AgentIterationMetrics,
    ParseStartMetrics,
    ParseEndMetrics,
    ParseValidationMetrics,
    BatchStartMetrics,
    BatchEndMetrics,
    BatchDiscoveryMetrics,
    HandleOpenMetrics,
    HandleCloseMetrics,
)


class TestBaseMetrics:
    """Test base metrics class that all others inherit from."""
    
    def test_base_metrics_includes_run_id_and_timestamp(self):
        """Test that BaseMetrics includes run_id and auto-generated timestamp."""
        metrics = BaseMetrics(run_id="run_123")
        assert metrics.run_id == "run_123"
        assert isinstance(metrics.timestamp, datetime)
    
    def test_base_metrics_requires_run_id(self):
        """Test that BaseMetrics requires run_id parameter."""
        with pytest.raises(ValidationError):
            BaseMetrics()


class TestLLMMetrics:
    """Test LLM-related metrics models."""
    
    @pytest.mark.parametrize("model_name,prompt_bytes,model_version", [
        pytest.param("gpt-4", 1024, "0613", id="with_version"),
        pytest.param("gpt-3.5-turbo", 512, None, id="without_version"),
        pytest.param("azure-gpt-4", 2048, "1106", id="azure_model"),
    ])
    def test_llm_start_metrics_success_cases(self, model_name, prompt_bytes, model_version):
        """Test LLM start metrics with various configurations."""
        metrics = LLMStartMetrics(
            run_id="run_123",
            model_name=model_name,
            prompt_bytes=prompt_bytes,
            model_version=model_version
        )
        assert metrics.model_name == model_name
        assert metrics.prompt_bytes == prompt_bytes
        assert metrics.model_version == model_version
    
    @pytest.mark.parametrize("tokens_prompt,tokens_completion,total_tokens", [
        pytest.param(100, 50, 150, id="normal_usage"),
        pytest.param(0, 0, 0, id="zero_tokens"),
        pytest.param(5000, 2000, 7000, id="large_usage"),
    ])
    def test_llm_usage_metrics_success_cases(self, tokens_prompt, tokens_completion, total_tokens):
        """Test LLM usage metrics with various token counts."""
        metrics = LLMUsageMetrics(
            run_id="run_123",
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion,
            total_tokens=total_tokens
        )
        assert metrics.tokens_prompt == tokens_prompt
        assert metrics.tokens_completion == tokens_completion
        assert metrics.total_tokens == total_tokens
    
    @pytest.mark.parametrize("status,duration_ms", [
        pytest.param("ok", 123.45, id="success"),
        pytest.param("error", 45.67, id="error"),
    ])
    def test_llm_end_metrics_success_cases(self, status, duration_ms):
        """Test LLM end metrics with valid status values."""
        metrics = LLMEndMetrics(
            run_id="run_123",
            status=status,
            duration_ms=duration_ms
        )
        assert metrics.status == status
        assert metrics.duration_ms == duration_ms
    
    def test_llm_end_metrics_invalid_status(self):
        """Test LLM end metrics rejects invalid status values."""
        with pytest.raises(ValidationError):
            LLMEndMetrics(
                run_id="run_123",
                status="pending",
                duration_ms=100.0
            )
    
    @pytest.mark.parametrize("error_type,error_message", [
        pytest.param("RateLimitError", "Rate limit exceeded", id="rate_limit"),
        pytest.param("TimeoutError", "Request timeout", id="timeout"),
        pytest.param("ValueError", "Invalid input", id="value_error"),
    ])
    def test_llm_error_metrics_success_cases(self, error_type, error_message):
        """Test LLM error metrics with various error types."""
        metrics = LLMErrorMetrics(
            run_id="run_123",
            error_type=error_type,
            error_message=error_message
        )
        assert metrics.error_type == error_type
        assert metrics.error_message == error_message


class TestToolMetrics:
    """Test tool-related metrics models."""
    
    @pytest.mark.parametrize("tool_name,input_bytes,arguments_passed", [
        pytest.param("read_file", 256, {"file_path": "test.txt"}, id="with_arguments"),
        pytest.param("list_dir", 128, None, id="without_arguments"),
        pytest.param("search_files", 512, {"pattern": "*.py", "max": 10}, id="complex_arguments"),
    ])
    def test_tool_start_metrics_success_cases(self, tool_name, input_bytes, arguments_passed):
        """Test tool start metrics with various configurations."""
        metrics = ToolStartMetrics(
            run_id="run_123",
            tool_name=tool_name,
            input_bytes=input_bytes,
            arguments_passed=arguments_passed
        )
        assert metrics.tool_name == tool_name
        assert metrics.input_bytes == input_bytes
        assert metrics.arguments_passed == arguments_passed
    
    @pytest.mark.parametrize("tool_name,status,duration_ms,output_bytes,result_meta", [
        pytest.param("read_file", "ok", 45.5, 1024, {"lines": 10}, id="success_with_meta"),
        pytest.param("write_file", "ok", 23.1, 0, {}, id="success_empty_meta"),
        pytest.param("parse_json", "error", 12.3, 0, {}, id="error_status"),
    ])
    def test_tool_end_metrics_success_cases(self, tool_name, status, duration_ms, output_bytes, result_meta):
        """Test tool end metrics with various outcomes."""
        metrics = ToolEndMetrics(
            run_id="run_123",
            tool_name=tool_name,
            status=status,
            duration_ms=duration_ms,
            output_bytes=output_bytes,
            result_meta=result_meta
        )
        assert metrics.tool_name == tool_name
        assert metrics.status == status
        assert metrics.duration_ms == duration_ms
        assert metrics.output_bytes == output_bytes
        assert isinstance(metrics.result_meta, dict)
    
    def test_tool_end_metrics_invalid_status(self):
        """Test tool end metrics rejects invalid status values."""
        with pytest.raises(ValidationError):
            ToolEndMetrics(
                run_id="run_123",
                tool_name="test",
                status="running",
                duration_ms=100.0,
                output_bytes=500
            )
    
    @pytest.mark.parametrize("tool_name,error_type,error_message", [
        pytest.param("read_file", "FileNotFoundError", "File not found", id="file_not_found"),
        pytest.param("write_file", "PermissionError", "Permission denied", id="permission_error"),
        pytest.param("parse_json", "ValueError", "Invalid JSON", id="value_error"),
    ])
    def test_tool_error_metrics_success_cases(self, tool_name, error_type, error_message):
        """Test tool error metrics with various error types."""
        metrics = ToolErrorMetrics(
            run_id="run_123",
            tool_name=tool_name,
            error_type=error_type,
            error_message=error_message
        )
        assert metrics.tool_name == tool_name
        assert metrics.error_type == error_type
        assert metrics.error_message == error_message


class TestAgentMetrics:
    """Test agent-related metrics models."""
    
    @pytest.mark.parametrize("input_keys,input_byte_counts", [
        pytest.param({"query": "test"}, {"query": 100}, id="single_input"),
        pytest.param({"query": "test", "context": "data"}, {"query": 100, "context": 200}, id="multiple_inputs"),
        pytest.param({"input": "value"}, {}, id="empty_byte_counts"),
    ])
    def test_agent_start_metrics_success_cases(self, input_keys, input_byte_counts):
        """Test agent start metrics with various input configurations."""
        metrics = AgentStartMetrics(
            run_id="run_123",
            input_keys=input_keys,
            input_byte_counts=input_byte_counts
        )
        assert metrics.input_keys == input_keys
        assert isinstance(metrics.input_byte_counts, dict)
    
    @pytest.mark.parametrize("status,duration_ms,output_keys,output_sizes", [
        pytest.param("ok", 500.0, ["output"], {"output": 1000}, id="success"),
        pytest.param("error", 250.0, [], {}, id="error_no_output"),
        pytest.param("ok", 1000.0, ["result", "metadata"], {"result": 500, "metadata": 200}, id="multiple_outputs"),
    ])
    def test_agent_end_metrics_success_cases(self, status, duration_ms, output_keys, output_sizes):
        """Test agent end metrics with various outcomes."""
        metrics = AgentEndMetrics(
            run_id="run_123",
            status=status,
            duration_ms=duration_ms,
            output_keys=output_keys,
            output_sizes=output_sizes
        )
        assert metrics.status == status
        assert metrics.duration_ms == duration_ms
        assert metrics.output_keys == output_keys
        assert metrics.output_sizes == output_sizes
    
    def test_agent_end_metrics_invalid_status(self):
        """Test agent end metrics rejects invalid status values."""
        with pytest.raises(ValidationError):
            AgentEndMetrics(
                run_id="run_123",
                status="pending",
                duration_ms=100.0,
                output_keys=[],
                output_sizes={}
            )
    
    @pytest.mark.parametrize("tokens_successful,tokens_billable", [
        pytest.param(1000, 1000, id="no_failed_calls"),
        pytest.param(1000, 1200, id="with_failed_calls"),
        pytest.param(0, 100, id="all_failed"),
    ])
    def test_agent_token_summary_success_cases(self, tokens_successful, tokens_billable):
        """Test agent token summary with various token scenarios."""
        metrics = AgentTokenSummaryMetrics(
            run_id="run_123",
            tokens_successful=tokens_successful,
            tokens_billable_estimate=tokens_billable
        )
        assert metrics.tokens_successful == tokens_successful
        assert metrics.tokens_billable_estimate == tokens_billable
        assert metrics.tokens_billable_estimate >= metrics.tokens_successful
    
    @pytest.mark.parametrize("iteration,action_type,action_summary,obs_summary", [
        pytest.param(1, "tool_call", "read_file(test.txt)", "", id="tool_action"),
        pytest.param(2, "finish", "", "Success", id="finish_action"),
        pytest.param(3, "tool_call", "search(*.py)", "Found 5 files", id="with_observation"),
    ])
    def test_agent_iteration_metrics_success_cases(self, iteration, action_type, action_summary, obs_summary):
        """Test agent iteration metrics with various action types."""
        metrics = AgentIterationMetrics(
            run_id="run_123",
            iteration_number=iteration,
            action_type=action_type,
            action_input_summary=action_summary,
            observation_summary=obs_summary
        )
        assert metrics.iteration_number == iteration
        assert metrics.action_type == action_type
        assert metrics.action_input_summary == action_summary
        assert metrics.observation_summary == obs_summary


class TestParseMetrics:
    """Test parsing/validation-related metrics models."""
    
    @pytest.mark.parametrize("schema_name,schema_version", [
        pytest.param("LogSchema", "v1.0", id="with_version"),
        pytest.param("EventSchema", None, id="without_version"),
    ])
    def test_parse_start_metrics_success_cases(self, schema_name, schema_version):
        """Test parse start metrics with various schema configurations."""
        metrics = ParseStartMetrics(
            run_id="run_123",
            target_schema=schema_name,
            schema_version=schema_version
        )
        assert metrics.target_schema == schema_name
        assert metrics.schema_version == schema_version
    
    @pytest.mark.parametrize("schema_name,status,duration_ms,parsed_bytes", [
        pytest.param("LogSchema", "ok", 45.5, 1024, id="success"),
        pytest.param("EventSchema", "error", 23.1, 0, id="error"),
    ])
    def test_parse_end_metrics_success_cases(self, schema_name, status, duration_ms, parsed_bytes):
        """Test parse end metrics with various outcomes."""
        metrics = ParseEndMetrics(
            run_id="run_123",
            target_schema=schema_name,
            status=status,
            duration_ms=duration_ms,
            parsed_bytes=parsed_bytes
        )
        assert metrics.target_schema == schema_name
        assert metrics.status == status
        assert metrics.duration_ms == duration_ms
        assert metrics.parsed_bytes == parsed_bytes
    
    @pytest.mark.parametrize("errors_count,error_rate,top_errors", [
        pytest.param(0, 0.0, [], id="no_errors"),
        pytest.param(5, 0.05, [{"field": "name", "error": "required"}], id="few_errors"),
        pytest.param(100, 1.0, [{"field": "id", "error": "invalid"}], id="all_errors"),
        pytest.param(50, 0.5, [], id="empty_error_list"),
    ])
    def test_parse_validation_metrics_success_cases(self, errors_count, error_rate, top_errors):
        """Test parse validation metrics with various error scenarios."""
        metrics = ParseValidationMetrics(
            run_id="run_123",
            target_schema="TestSchema",
            errors_count=errors_count,
            top_n_field_errors=top_errors,
            error_rate=error_rate
        )
        assert metrics.errors_count == errors_count
        assert metrics.error_rate == error_rate
        assert isinstance(metrics.top_n_field_errors, list)
    
    @pytest.mark.parametrize("invalid_rate", [
        pytest.param(-0.1, id="negative_rate"),
        pytest.param(1.5, id="above_one"),
        pytest.param(2.0, id="way_above_one"),
    ])
    def test_parse_validation_metrics_error_rate_validation(self, invalid_rate):
        """Test parse validation metrics enforces error_rate bounds (0.0-1.0)."""
        with pytest.raises(ValidationError):
            ParseValidationMetrics(
                run_id="run_123",
                target_schema="TestSchema",
                errors_count=10,
                error_rate=invalid_rate
            )


class TestBatchMetrics:
    """Test batch processing-related metrics models."""
    
    @pytest.mark.parametrize("batch_num,lines_to_read", [
        pytest.param(1, 100, id="first_batch"),
        pytest.param(5, 1000, id="large_batch"),
        pytest.param(10, 50, id="small_batch"),
    ])
    def test_batch_start_metrics_success_cases(self, batch_num, lines_to_read):
        """Test batch start metrics with various batch configurations."""
        metrics = BatchStartMetrics(
            run_id="run_123",
            batch_number=batch_num,
            lines_to_read=lines_to_read
        )
        assert metrics.batch_number == batch_num
        assert metrics.lines_to_read == lines_to_read
    
    @pytest.mark.parametrize("batch_num,lines_read,cumulative,duration_ms", [
        pytest.param(1, 100, 100, 45.5, id="first_batch"),
        pytest.param(2, 100, 200, 50.2, id="second_batch"),
        pytest.param(5, 50, 450, 30.1, id="partial_batch"),
    ])
    def test_batch_end_metrics_success_cases(self, batch_num, lines_read, cumulative, duration_ms):
        """Test batch end metrics with various completion scenarios."""
        metrics = BatchEndMetrics(
            run_id="run_123",
            batch_number=batch_num,
            lines_read=lines_read,
            cumulative_lines_processed=cumulative,
            duration_ms=duration_ms
        )
        assert metrics.batch_number == batch_num
        assert metrics.lines_read == lines_read
        assert metrics.cumulative_lines_processed == cumulative
        assert metrics.duration_ms == duration_ms
    
    @pytest.mark.parametrize("batch_num,new_log_types,new_fields", [
        pytest.param(1, 5, 20, id="initial_discovery"),
        pytest.param(2, 2, 8, id="some_new_items"),
        pytest.param(5, 0, 0, id="no_new_items"),
    ])
    def test_batch_discovery_metrics_success_cases(self, batch_num, new_log_types, new_fields):
        """Test batch discovery metrics with various discovery scenarios."""
        metrics = BatchDiscoveryMetrics(
            run_id="run_123",
            batch_number=batch_num,
            new_log_types_found=new_log_types,
            new_fields_found=new_fields
        )
        assert metrics.batch_number == batch_num
        assert metrics.new_log_types_found == new_log_types
        assert metrics.new_fields_found == new_fields


class TestHandleMetrics:
    """Test file handle-related metrics models."""
    
    @pytest.mark.parametrize("handle_id,file_path,total_lines", [
        pytest.param("handle_123", "/path/to/file.jsonl", 1000, id="with_line_count"),
        pytest.param("handle_456", "/path/to/data.jsonl", None, id="without_line_count"),
    ])
    def test_handle_open_metrics_success_cases(self, handle_id, file_path, total_lines):
        """Test handle open metrics with various configurations."""
        metrics = HandleOpenMetrics(
            run_id="run_123",
            handle_id=handle_id,
            file_path=file_path,
            total_lines=total_lines
        )
        assert metrics.handle_id == handle_id
        assert metrics.file_path == file_path
        assert metrics.total_lines == total_lines
    
    @pytest.mark.parametrize("handle_id,lines_read,duration_ms", [
        pytest.param("handle_123", 1000, 5000.0, id="full_file"),
        pytest.param("handle_456", 500, 2500.0, id="partial_file"),
        pytest.param("handle_789", 0, 100.0, id="no_lines_read"),
    ])
    def test_handle_close_metrics_success_cases(self, handle_id, lines_read, duration_ms):
        """Test handle close metrics with various usage scenarios."""
        metrics = HandleCloseMetrics(
            run_id="run_123",
            handle_id=handle_id,
            total_lines_read=lines_read,
            duration_open_ms=duration_ms
        )
        assert metrics.handle_id == handle_id
        assert metrics.total_lines_read == lines_read
        assert metrics.duration_open_ms == duration_ms
