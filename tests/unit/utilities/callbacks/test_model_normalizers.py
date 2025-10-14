import pytest
from unittest.mock import Mock

from utilities.callbacks.model_normalizers import (
    AzureOpenAINormalizer,
    LLMResponseNormalizer
)
from utilities.callbacks.metrics_models import (
    LLMStartMetrics,
    LLMUsageMetrics,
    LLMEndMetrics,
    LLMErrorMetrics
)


class TestAzureOpenAINormalizer:
    """Test Azure OpenAI response normalization into metrics models."""
    
    @pytest.mark.parametrize("serialized,expected_model,expected_version,expected_bytes", [
        pytest.param(
            {'name': 'gpt-4', 'kwargs': {'model_version': '2024-02-15-preview'}},
            'gpt-4',
            '2024-02-15-preview',
            11,
            id="full_metadata"
        ),
        pytest.param(
            {'name': 'gpt-35-turbo', 'kwargs': {}},
            'gpt-35-turbo',
            None,
            11,
            id="no_version"
        ),
        pytest.param(
            {'kwargs': {}},
            'unknown',
            None,
            11,
            id="missing_name"
        ),
        pytest.param(
            {},
            'unknown',
            None,
            11,
            id="empty_dict"
        ),
    ])
    def test_normalize_start_success_cases(self, serialized, expected_model, expected_version, expected_bytes):
        """Test normalize_start with various serialized configurations."""
        normalizer = AzureOpenAINormalizer()
        prompts = ["test prompt"]
        
        metrics = normalizer.normalize_start(serialized, prompts, "run_123")
        
        assert isinstance(metrics, LLMStartMetrics)
        assert metrics.run_id == "run_123"
        assert metrics.model_name == expected_model
        assert metrics.model_version == expected_version
        assert metrics.prompt_bytes == expected_bytes
    
    def test_normalize_start_multiple_prompts(self):
        """Test normalize_start calculates total bytes for multiple prompts."""
        normalizer = AzureOpenAINormalizer()
        prompts = ["prompt one", "prompt two"]
        serialized = {'name': 'gpt-4'}
        
        metrics = normalizer.normalize_start(serialized, prompts, "run_123")
        
        assert metrics.prompt_bytes == 20
        assert metrics.model_name == "gpt-4"
    
    @pytest.mark.parametrize("response_setup,expected_prompt,expected_completion,expected_total", [
        pytest.param(
            lambda: _create_realistic_azure_response_with_usage_metadata(9338, 1419, 10757),
            9338,
            1419,
            10757,
            id="usage_metadata_realistic"
        ),
        pytest.param(
            lambda: _create_realistic_azure_response_with_llm_output(200, 75, 275),
            200,
            75,
            275,
            id="llm_output_fallback"
        ),
        pytest.param(
            lambda: _create_realistic_azure_response_with_response_metadata(150, 60, 210),
            150,
            60,
            210,
            id="response_metadata_fallback"
        ),
    ])
    def test_normalize_usage_success_cases(self, response_setup, expected_prompt, expected_completion, expected_total):
        """Test normalize_usage extracts tokens from different response structures."""
        normalizer = AzureOpenAINormalizer()
        mock_response = response_setup()
        
        metrics = normalizer.normalize_usage(mock_response, "run_123")
        
        assert isinstance(metrics, LLMUsageMetrics)
        assert metrics.run_id == "run_123"
        assert metrics.tokens_prompt == expected_prompt
        assert metrics.tokens_completion == expected_completion
        assert metrics.total_tokens == expected_total
    
    @pytest.mark.parametrize("response_setup", [
        pytest.param(lambda: _create_response_with_empty_llm_output(), id="empty_llm_output"),
        pytest.param(lambda: _create_response_with_no_generations(), id="no_generations"),
        pytest.param(lambda: _create_response_with_none_llm_output(), id="none_llm_output"),
    ])
    def test_normalize_usage_edge_cases(self, response_setup):
        """Test normalize_usage handles missing or incomplete token data."""
        normalizer = AzureOpenAINormalizer()
        mock_response = response_setup()
        
        metrics = normalizer.normalize_usage(mock_response, "run_123")
        
        assert isinstance(metrics, LLMUsageMetrics)
        assert metrics.run_id == "run_123"
        assert metrics.tokens_prompt == 0
        assert metrics.tokens_completion == 0
        assert metrics.total_tokens == 0
    
    def test_normalize_usage_partial_tokens(self):
        """Test normalize_usage returns available tokens even if some are missing."""
        normalizer = AzureOpenAINormalizer()
        mock_response = _create_response_with_partial_tokens()
        
        metrics = normalizer.normalize_usage(mock_response, "run_123")
        
        assert isinstance(metrics, LLMUsageMetrics)
        assert metrics.run_id == "run_123"
        assert metrics.tokens_prompt == 100
        assert metrics.tokens_completion == 0
        assert metrics.total_tokens == 0
    
    @pytest.mark.parametrize("has_generations,expected_status", [
        pytest.param(True, "ok", id="successful_response"),
        pytest.param(False, "error", id="empty_generations"),
    ])
    def test_normalize_end_success_cases(self, has_generations, expected_status):
        """Test normalize_end determines status based on generations."""
        normalizer = AzureOpenAINormalizer()
        mock_response = Mock()
        mock_response.generations = [Mock()] if has_generations else []
        
        metrics = normalizer.normalize_end(mock_response, "run_123", 123.45)
        
        assert isinstance(metrics, LLMEndMetrics)
        assert metrics.run_id == "run_123"
        assert metrics.status == expected_status
        assert metrics.duration_ms == 123.45
    
    @pytest.mark.parametrize("error,expected_type,expected_msg", [
        pytest.param(ValueError("Invalid input"), "ValueError", "Invalid input", id="value_error"),
        pytest.param(TimeoutError("Request timeout"), "TimeoutError", "Request timeout", id="timeout_error"),
        pytest.param(Exception("Unknown error"), "Exception", "Unknown error", id="generic_exception"),
    ])
    def test_normalize_error_success_cases(self, error, expected_type, expected_msg):
        """Test normalize_error extracts error type and message."""
        normalizer = AzureOpenAINormalizer()
        
        metrics = normalizer.normalize_error(error, "run_123")
        
        assert isinstance(metrics, LLMErrorMetrics)
        assert metrics.run_id == "run_123"
        assert metrics.error_type == expected_type
        assert metrics.error_message == expected_msg


def _create_realistic_azure_response_with_usage_metadata(prompt_tokens, completion_tokens, total_tokens):
    """
    Create mock response matching actual Azure OpenAI structure (LangChain 0.3+).
    Based on real production response captured from logs.
    """
    mock_response = Mock()
    mock_response.llm_output = {
        'token_usage': None,
        'system_fingerprint': None,
        'model_name': 'gpt-5-2025-08-07'
    }
    
    mock_gen = Mock()
    mock_message = Mock()
    
    mock_message.usage_metadata = {
        'input_tokens': prompt_tokens,
        'output_tokens': completion_tokens,
        'total_tokens': total_tokens,
        'input_token_details': {
            'audio': 0,
            'cache_read': int(prompt_tokens * 0.9)
        },
        'output_token_details': {
            'audio': 0,
            'reasoning': int(completion_tokens * 0.1)
        }
    }
    
    mock_message.response_metadata = {
        'finish_reason': 'tool_calls',
        'model_name': 'gpt-5-2025-08-07',
        'system_fingerprint': None
    }
    
    mock_message.id = 'run--9a793c01-32ef-4f7e-8241-c3d90885180c'
    mock_message.content = ''
    mock_message.additional_kwargs = {'tool_calls': []}
    
    mock_gen.message = mock_message
    mock_response.generations = [[mock_gen]]
    
    return mock_response


def _create_realistic_azure_response_with_llm_output(prompt_tokens, completion_tokens, total_tokens):
    """
    Create mock response with token_usage in llm_output (older LangChain versions).
    Includes realistic Azure-specific fields.
    """
    mock_response = Mock()
    mock_response.llm_output = {
        'token_usage': {
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'total_tokens': total_tokens
        },
        'model_name': 'gpt-4-turbo',
        'system_fingerprint': 'fp_abc123'
    }
    mock_response.generations = []
    return mock_response


def _create_realistic_azure_response_with_response_metadata(prompt_tokens, completion_tokens, total_tokens):
    """
    Create mock response with token_usage in response_metadata (alternative older format).
    Includes realistic Azure-specific metadata fields.
    """
    mock_response = Mock()
    mock_response.llm_output = {
        'model_name': 'gpt-35-turbo',
        'system_fingerprint': None
    }
    
    mock_gen = Mock()
    mock_message = Mock()
    
    mock_message.response_metadata = {
        'token_usage': {
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'total_tokens': total_tokens
        },
        'finish_reason': 'stop',
        'model_name': 'gpt-35-turbo',
        'content_filter_results': {}
    }
    
    mock_message.usage_metadata = None
    mock_message.content = 'Response text here'
    mock_message.additional_kwargs = {}
    
    mock_gen.message = mock_message
    mock_response.generations = [[mock_gen]]
    
    return mock_response


def _create_response_with_empty_llm_output():
    """Create mock response with empty llm_output."""
    mock_response = Mock()
    mock_response.llm_output = {}
    mock_response.generations = []
    return mock_response


def _create_response_with_no_generations():
    """Create mock response with no generations."""
    mock_response = Mock()
    mock_response.llm_output = None
    mock_response.generations = []
    return mock_response


def _create_response_with_none_llm_output():
    """Create mock response with None llm_output."""
    mock_response = Mock()
    mock_response.llm_output = None
    mock_response.generations = []
    return mock_response


def _create_response_with_partial_tokens():
    """Create mock response with incomplete token data."""
    mock_response = Mock()
    mock_response.llm_output = {
        'token_usage': {
            'prompt_tokens': 100
        }
    }
    mock_response.generations = []
    return mock_response
