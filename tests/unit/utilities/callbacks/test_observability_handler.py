import pytest
import logging
import time
from unittest.mock import Mock, patch
from langchain_core.agents import AgentAction, AgentFinish

from utilities.callbacks.observability_handler import ObservabilityCallbackHandler
from utilities.callbacks.tokens_counter import TokensCounter
from utilities.callbacks.model_normalizers import AzureOpenAINormalizer
from utilities.callbacks.metrics_models import (
    LLMUsageMetrics,
    LLMStartMetrics,
    LLMEndMetrics,
    LLMErrorMetrics
)
from utilities.logger import TRACE


class TestObservabilityHandler:
    """Test the main observability callback handler for LangChain agents."""
    
    @pytest.fixture
    def mock_logger(self):
        logger = Mock(spec=logging.Logger)
        logger.isEnabledFor = Mock(return_value=False)
        logger.getEffectiveLevel = Mock(return_value=logging.DEBUG)
        return logger
    
    @pytest.fixture
    def mock_normalizer(self):
        normalizer = Mock(spec=AzureOpenAINormalizer)
        return normalizer
    
    @pytest.fixture
    def handler(self, mock_logger, mock_normalizer):
        return ObservabilityCallbackHandler(
            logger=mock_logger,
            run_id="run_test123",
            normalizer=mock_normalizer
        )
    
    def test_handler_initialization(self, handler):
        """Test handler initializes with correct default state."""
        assert handler.run_id == "run_test123"
        assert isinstance(handler.token_counter, TokensCounter)
        assert handler._iteration_count == 0
        assert handler._agent_start_time is None
        assert handler._llm_start_time is None
    
    def test_on_chain_start_logs_agent_start(self, handler, mock_logger):
        """Test on_chain_start logs agent start metrics."""
        inputs = {"input": "test query", "context": "test context"}
        handler.on_chain_start(serialized={}, inputs=inputs)
        assert handler._agent_start_time is not None
        assert mock_logger.info.called
        assert mock_logger.debug.called
        info_call = mock_logger.info.call_args[0][0]
        assert "agent.start" in info_call
        assert "run_test123" in info_call
    
    def test_on_chain_end_logs_token_summary(self, handler, mock_logger):
        """Test on_chain_end logs token summary with successful and failed tokens."""
        handler._agent_start_time = time.time()
        handler.token_counter.total_tokens = 500
        handler.token_counter.failed_llm_calls_tokens = 100
        outputs = {"output": "test result"}
        handler.on_chain_end(outputs=outputs)
        assert mock_logger.info.call_count >= 2
        calls = [call[0][0] for call in mock_logger.info.call_args_list]
        assert any("agent.end" in call for call in calls)
        assert any("agent.tokens_summary" in call and "tokens_successful=500" in call for call in calls)
    
    @pytest.mark.parametrize("error_class,error_message", [
        (ValueError, "Invalid value"),
        (RuntimeError, "Runtime error occurred"),
        (Exception, "Generic exception")
    ])
    def test_on_chain_error_logs_error_status(self, handler, mock_logger, error_class, error_message):
        """Test on_chain_error logs agent error with various exception types."""
        handler._agent_start_time = time.time()
        test_error = error_class(error_message)
        handler.on_chain_error(error=test_error)
        assert mock_logger.error.called
        error_call = mock_logger.error.call_args[0][0]
        assert "agent.end" in error_call
        assert "status=error" in error_call
        assert error_class.__name__ in error_call
    
    def test_on_llm_start_logs_model_info(self, handler, mock_logger, mock_normalizer):
        """Test on_llm_start logs model name and prompt size."""
        mock_start = LLMStartMetrics(
            run_id="run_test123",
            model_name="gpt-4",
            prompt_bytes=1024
        )
        mock_normalizer.normalize_start.return_value = mock_start
        serialized = {"name": "gpt-4"}
        prompts = ["test prompt"]
        handler.on_llm_start(serialized=serialized, prompts=prompts)
        assert handler._llm_start_time is not None
        assert mock_logger.debug.called
        debug_call = mock_logger.debug.call_args[0][0]
        assert "llm.start" in debug_call
        assert "gpt-4" in debug_call
    
    def test_on_llm_end_updates_token_counter(self, handler, mock_normalizer):
        """Test on_llm_end updates token collector with usage metrics."""
        handler._llm_start_time = time.time()
        mock_usage = LLMUsageMetrics(
            run_id="run_test123",
            tokens_prompt=100,
            tokens_completion=50,
            total_tokens=150
        )
        mock_end = LLMEndMetrics(
            run_id="run_test123",
            status="ok",
            duration_ms=100.0
        )
        mock_normalizer.normalize_usage.return_value = mock_usage
        mock_normalizer.normalize_end.return_value = mock_end
        mock_response = Mock()
        handler.on_llm_end(mock_response)
        assert handler.token_counter.total_tokens == 150
        assert handler.token_counter.total_prompt_tokens == 100
        assert handler.token_counter.total_completion_tokens == 50
    
    @pytest.mark.parametrize("error_type,error_message,has_response,expected_failed_tokens", [
        ("RateLimitError", "Rate limit exceeded", True, 75),
        ("ConnectionError", "Connection timeout", False, 0),
        ("TimeoutError", "Request timeout", True, 50),
    ])
    def test_on_llm_error_tracks_failed_tokens(self, handler, mock_logger, mock_normalizer, error_type, error_message, has_response, expected_failed_tokens):
        """Test on_llm_error tracks failed tokens for billing estimates."""
        mock_error_metrics = LLMErrorMetrics(
            run_id="run_test123",
            error_type=error_type,
            error_message=error_message
        )
        mock_normalizer.normalize_error.return_value = mock_error_metrics
        
        kwargs = {}
        if has_response:
            mock_usage = LLMUsageMetrics(
                run_id="run_test123",
                tokens_prompt=expected_failed_tokens,
                tokens_completion=0,
                total_tokens=expected_failed_tokens
            )
            mock_normalizer.normalize_usage.return_value = mock_usage
            kwargs['response'] = Mock()
        
        test_error = Exception(error_message)
        handler.on_llm_error(error=test_error, **kwargs)
        assert handler.token_counter.failed_llm_calls_tokens == expected_failed_tokens
        assert mock_logger.error.called
        error_call = mock_logger.error.call_args[0][0]
        assert "llm.error" in error_call
        assert error_type in error_call
    
    def test_on_tool_start_logs_tool_info(self, handler, mock_logger):
        """Test on_tool_start logs tool name and argument keys."""
        handler.on_tool_start(
            serialized={"name": "read_file"},
            input_str='{"file_path": "test.txt", "max_lines": 100}'
        )
        assert mock_logger.debug.called
        debug_call = mock_logger.debug.call_args[0][0]
        assert "tool.start" in debug_call
        assert "read_file" in debug_call
        assert "arg_keys" in debug_call
        assert "file_path" in debug_call or "max_lines" in debug_call
    
    @pytest.mark.parametrize("log_level,should_log_trace", [
        (TRACE, True),
        (logging.DEBUG, False),
        (logging.INFO, False)
    ])
    def test_on_tool_start_trace_behavior(self, mock_logger, mock_normalizer, log_level, should_log_trace):
        """Test on_tool_start logs full arguments only at TRACE level."""
        mock_logger.isEnabledFor = Mock(side_effect=lambda level: level >= log_level)
        handler = ObservabilityCallbackHandler(
            logger=mock_logger,
            run_id="run_test123",
            normalizer=mock_normalizer
        )
        handler.on_tool_start(
            serialized={"name": "test_tool"},
            input_str='{"arg1": "value1"}'
        )
        if should_log_trace:
            assert mock_logger.trace.called
            trace_call = mock_logger.trace.call_args[0][0]
            assert "tool.start" in trace_call
        else:
            assert not mock_logger.trace.called
    
    def test_on_tool_end_logs_duration_and_output_size(self, handler, mock_logger):
        """Test on_tool_end logs duration and output preview at DEBUG level."""
        handler._tool_start_times["test_run"] = time.time() - 0.1
        handler.on_tool_end(
            output="test output content",
            name="read_file",
            run_id="test_run"
        )
        assert mock_logger.debug.called
        debug_call = mock_logger.debug.call_args[0][0]
        assert "tool.end" in debug_call
        assert "read_file" in debug_call
        assert "status=ok" in debug_call
        assert "duration_ms" in debug_call
        assert "output_preview" in debug_call
        assert "test output content" in debug_call
    
    @pytest.mark.parametrize("log_level,output_length,should_log_output", [
        (TRACE, 2000, True),
        (logging.DEBUG, 2000, False),
        (TRACE, 500, True),
    ])
    def test_on_tool_end_trace_behavior(self, mock_logger, mock_normalizer, log_level, output_length, should_log_output):
        """Test on_tool_end logs full output only at TRACE level."""
        mock_logger.isEnabledFor = Mock(side_effect=lambda level: level >= log_level)
        handler = ObservabilityCallbackHandler(
            logger=mock_logger,
            run_id="run_test123",
            normalizer=mock_normalizer
        )
        handler._tool_start_times["test_run"] = time.time()
        long_output = "x" * output_length
        handler.on_tool_end(
            output=long_output,
            name="test_tool",
            run_id="test_run"
        )
        if should_log_output:
            assert mock_logger.trace.call_count >= 1
            trace_calls = [call[0][0] for call in mock_logger.trace.call_args_list]
            assert any("tool.output" in call for call in trace_calls)
        else:
            assert not mock_logger.trace.called
    
    def test_on_tool_end_logs_full_output_at_trace(self, mock_logger, mock_normalizer):
        """Test on_tool_end logs complete output without truncation at TRACE."""
        mock_logger.isEnabledFor = Mock(side_effect=lambda level: level >= TRACE)
        handler = ObservabilityCallbackHandler(
            logger=mock_logger,
            run_id="run_test123",
            normalizer=mock_normalizer
        )
        handler._tool_start_times["test_run"] = time.time()
        full_output = "A" * 5000
        handler.on_tool_end(
            output=full_output,
            name="test_tool",
            run_id="test_run"
        )
        assert mock_logger.trace.call_count == 2
        trace_calls = [call[0][0] for call in mock_logger.trace.call_args_list]
        output_log = [call for call in trace_calls if "tool.output" in call][0]
        assert full_output in output_log
        assert len([c for c in output_log if c == 'A']) == 5000
    
    def test_on_tool_end_debug_shows_preview_not_full(self, mock_logger, mock_normalizer):
        """Test on_tool_end shows 200-char preview at DEBUG, not full output."""
        mock_logger.isEnabledFor = Mock(side_effect=lambda level: level >= logging.DEBUG)
        handler = ObservabilityCallbackHandler(
            logger=mock_logger,
            run_id="run_test123",
            normalizer=mock_normalizer
        )
        handler._tool_start_times["test_run"] = time.time()
        long_output = "B" * 5000
        handler.on_tool_end(
            output=long_output,
            name="test_tool",
            run_id="test_run"
        )
        assert mock_logger.debug.called
        debug_call = mock_logger.debug.call_args[0][0]
        assert "output_preview" in debug_call
        assert "B" * 200 in debug_call
        assert "B" * 5000 not in debug_call
        assert not mock_logger.trace.called
    
    @pytest.mark.parametrize("error_class,error_message,tool_name", [
        (FileNotFoundError, "File not found", "read_file"),
        (PermissionError, "Permission denied", "write_file"),
        (ValueError, "Invalid input", "parse_json")
    ])
    def test_on_tool_error_logs_error_info(self, handler, mock_logger, error_class, error_message, tool_name):
        """Test on_tool_error logs tool errors with various exception types."""
        test_error = error_class(error_message)
        handler.on_tool_error(error=test_error, name=tool_name)
        assert mock_logger.error.called
        error_call = mock_logger.error.call_args[0][0]
        assert "tool.error" in error_call
        assert tool_name in error_call
        assert error_class.__name__ in error_call
    
    @pytest.mark.parametrize("log_level,should_log,expected_iteration_count", [
        (TRACE, True, 1),
        (logging.DEBUG, False, 0),
        (logging.INFO, False, 0)
    ])
    def test_on_agent_action_trace_behavior(self, mock_logger, mock_normalizer, log_level, should_log, expected_iteration_count):
        """Test on_agent_action logs iteration details only at TRACE level."""
        mock_logger.isEnabledFor = Mock(side_effect=lambda level: level >= log_level)
        handler = ObservabilityCallbackHandler(
            logger=mock_logger,
            run_id="run_test123",
            normalizer=mock_normalizer
        )
        action = AgentAction(tool="read_file", tool_input={"file": "test.txt"}, log="")
        handler.on_agent_action(action=action)
        assert handler._iteration_count == expected_iteration_count
        if should_log:
            assert mock_logger.trace.called
            assert mock_logger.trace.call_count == 2
            trace_calls = [call[0][0] for call in mock_logger.trace.call_args_list]
            assert any("agent.iteration" in call and "iteration=1" in call for call in trace_calls)
            assert any("agent.iteration" in call and "run_test123" in call for call in trace_calls)
        else:
            assert not mock_logger.trace.called
    
    @pytest.mark.parametrize("log_level,should_log,expected_iteration_count", [
        (TRACE, True, 1),
        (logging.DEBUG, False, 0),
        (logging.INFO, False, 0)
    ])
    def test_on_agent_finish_trace_behavior(self, mock_logger, mock_normalizer, log_level, should_log, expected_iteration_count):
        """Test on_agent_finish logs completion details only at TRACE level."""
        mock_logger.isEnabledFor = Mock(side_effect=lambda level: level >= log_level)
        handler = ObservabilityCallbackHandler(
            logger=mock_logger,
            run_id="run_test123",
            normalizer=mock_normalizer
        )
        finish = AgentFinish(return_values={"output": "final result"}, log="")
        handler.on_agent_finish(finish=finish)
        assert handler._iteration_count == expected_iteration_count
        if should_log:
            assert mock_logger.trace.called
            assert mock_logger.trace.call_count == 2
            trace_calls = [call[0][0] for call in mock_logger.trace.call_args_list]
            assert any("agent.iteration" in call and "action=finish" in call for call in trace_calls)
            assert any("agent.iteration" in call and "run_test123" in call for call in trace_calls)
        else:
            assert not mock_logger.trace.called
    
    def test_multiple_llm_calls_aggregate_tokens(self, handler, mock_normalizer):
        """Test multiple LLM calls properly aggregate tokens in collector."""
        handler._llm_start_time = time.time()
        for i in range(3):
            mock_usage = LLMUsageMetrics(
                run_id="run_test123",
                tokens_prompt=100,
                tokens_completion=50,
                total_tokens=150
            )
            mock_end = LLMEndMetrics(
                run_id="run_test123",
                status="ok",
                duration_ms=100.0
            )
            mock_normalizer.normalize_usage.return_value = mock_usage
            mock_normalizer.normalize_end.return_value = mock_end
            handler.on_llm_end(Mock())
        assert handler.token_counter.total_tokens == 450
        assert handler.token_counter.total_prompt_tokens == 300
        assert handler.token_counter.total_completion_tokens == 150
    
    def test_error_handling_in_callbacks_does_not_crash(self, handler, mock_logger):
        """Test that callback errors are logged but don't crash the handler."""
        handler.normalizer.normalize_usage = Mock(side_effect=Exception("Test error"))
        mock_response = Mock()
        handler.on_llm_end(mock_response)
        assert mock_logger.error.called
        handler.on_chain_start(serialized=None, inputs={"bad": "data"})
        assert mock_logger.error.call_count >= 1
