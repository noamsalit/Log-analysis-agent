"""Tests for the CLI runner script."""
import pytest
from unittest.mock import Mock, patch, mock_open
from pathlib import Path
import tempfile
import os

from run_schema_agent import (
    create_llm_client,
    load_yaml_config,
    parse_index_arg,
    run_single_index
)


class TestCreateLLMClient:
    """Test LLM client creation with various configurations."""
    
    @pytest.mark.parametrize("provider,env_vars,expected_calls,temperature", [
        pytest.param(
            "azure_openai",
            {
                "AZURE_OPENAI_API_KEY": "test-key",
                "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
                "AZURE_OPENAI_API_VERSION": "2024-02-15-preview",
                "AZURE_OPENAI_API_DEPLOYMENT_NAME": "gpt-4"
            },
            {
                "api_key": "test-key",
                "azure_endpoint": "https://test.openai.azure.com",
                "api_version": "2024-02-15-preview",
                "azure_deployment": "gpt-4",
            },
            None,
            id="azure_openai_from_env_default_temp"
        ),
        pytest.param(
            "azure_openai",
            {},
            {
                "api_key": "override-key",
                "azure_endpoint": "https://override.openai.azure.com",
                "api_version": "2024-05-01",
                "azure_deployment": "gpt-35-turbo",
                "temperature": 0.5
            },
            0.5,
            id="azure_openai_with_overrides"
        ),
    ])
    def test_create_llm_client_success_cases(
        self, provider, env_vars, expected_calls, temperature
    ):
        """Test creating LLM client with various valid configurations."""
        with patch.dict(os.environ, env_vars, clear=True):
            with patch('run_schema_agent.AzureChatOpenAI') as mock_azure:
                if "override" in str(expected_calls.get("api_key", "")):
                    create_llm_client(
                        provider=provider,
                        api_key=expected_calls["api_key"],
                        endpoint=expected_calls["azure_endpoint"],
                        model=expected_calls["azure_deployment"],
                        api_version=expected_calls["api_version"],
                        temperature=temperature
                    )
                else:
                    create_llm_client(provider=provider, temperature=temperature)
                
                mock_azure.assert_called_once()
                call_kwargs = mock_azure.call_args[1]
                
                for key, value in expected_calls.items():
                    assert call_kwargs[key] == value
                
                assert call_kwargs["model_kwargs"] == {
                    "stream_options": {"include_usage": True}
                }
    
    def test_create_llm_client_unsupported_provider(self):
        """Test creating LLM client with unsupported provider raises error."""
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            create_llm_client(provider="unsupported_provider")


class TestLoadYAMLConfig:
    """Test YAML configuration file loading."""
    
    @pytest.mark.parametrize("yaml_content,expected_result", [
        pytest.param(
            """
            - index_name: test_index
              log_file: /path/to/logs.jsonl
            """,
            [{"index_name": "test_index", "log_file": "/path/to/logs.jsonl"}],
            id="single_dataset"
        ),
        pytest.param(
            """
            - index_name: index1
              log_file: /path/to/logs1.jsonl
            - index_name: index2
              log_file: /path/to/logs2.jsonl
            """,
            [
                {"index_name": "index1", "log_file": "/path/to/logs1.jsonl"},
                {"index_name": "index2", "log_file": "/path/to/logs2.jsonl"}
            ],
            id="multiple_datasets"
        ),
    ])
    def test_load_yaml_config_success_cases(self, yaml_content, expected_result):
        """Test loading valid YAML configurations."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.yaml', delete=False
        ) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            result = load_yaml_config(temp_path)
            assert result == expected_result
        finally:
            os.unlink(temp_path)
    
    @pytest.mark.parametrize("yaml_content,error_match", [
        pytest.param(
            "not_a_list: true",
            "YAML config must be a list",
            id="not_a_list"
        ),
        pytest.param(
            """
            - index_name: test_index
            """,
            "must have 'index_name' and 'log_file' keys",
            id="missing_log_file"
        ),
        pytest.param(
            """
            - log_file: /path/to/logs.jsonl
            """,
            "must have 'index_name' and 'log_file' keys",
            id="missing_index_name"
        ),
    ])
    def test_load_yaml_config_error_cases(self, yaml_content, error_match):
        """Test loading invalid YAML configurations raises appropriate errors."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.yaml', delete=False
        ) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError, match=error_match):
                load_yaml_config(temp_path)
        finally:
            os.unlink(temp_path)


class TestParseIndexArg:
    """Test parsing of --index command-line arguments."""
    
    @pytest.mark.parametrize("index_str,expected_result", [
        pytest.param(
            "test_index=/path/to/logs.jsonl",
            {"index_name": "test_index", "log_file": "/path/to/logs.jsonl"},
            id="simple_path"
        ),
        pytest.param(
            "endpoint=/Users/user/logs/endpoint.jsonl",
            {
                "index_name": "endpoint",
                "log_file": "/Users/user/logs/endpoint.jsonl"
            },
            id="absolute_path"
        ),
        pytest.param(
            "test=path/with/equals=sign.jsonl",
            {
                "index_name": "test",
                "log_file": "path/with/equals=sign.jsonl"
            },
            id="path_with_equals_sign"
        ),
        pytest.param(
            " spaced_index = /path/to/logs.jsonl ",
            {
                "index_name": "spaced_index",
                "log_file": "/path/to/logs.jsonl"
            },
            id="with_whitespace"
        ),
    ])
    def test_parse_index_arg_success_cases(self, index_str, expected_result):
        """Test parsing valid --index arguments."""
        result = parse_index_arg(index_str)
        assert result == expected_result
    
    @pytest.mark.parametrize("index_str", [
        pytest.param("invalid_format", id="no_equals_sign"),
        pytest.param("", id="empty_string"),
    ])
    def test_parse_index_arg_error_cases(self, index_str):
        """Test parsing invalid --index arguments raises error."""
        with pytest.raises(ValueError, match="Invalid --index format"):
            parse_index_arg(index_str)


class TestRunSingleIndex:
    """Test running the agent on a single index."""
    
    def test_run_single_index_success(self):
        """Test successful execution on a single index."""
        mock_result = Mock()
        mock_result.model_dump_json.return_value = '{"log_types": {}}'
        mock_result.log_types = {"type1": {}, "type2": {}}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            with patch('run_schema_agent.run_agent', return_value=mock_result):
                with patch('run_schema_agent.logger') as mock_logger:
                    result = run_single_index(
                        index_name="test_index",
                        log_file="/path/to/logs.jsonl",
                        output_dir=output_dir,
                        llm_client=Mock(),
                        overwrite=False
                    )
                    
                    assert result is True
                    output_file = output_dir / "test_index_schema.json"
                    assert output_file.exists()
                    
                    mock_logger.info.assert_called()
    
    def test_run_single_index_file_exists_no_overwrite(self):
        """Test skipping when output file exists and overwrite is False."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            output_file = output_dir / "test_index_schema.json"
            output_file.write_text('{"existing": "data"}')
            
            with patch('run_schema_agent.logger') as mock_logger:
                result = run_single_index(
                    index_name="test_index",
                    log_file="/path/to/logs.jsonl",
                    output_dir=output_dir,
                    llm_client=Mock(),
                    overwrite=False
                )
                
                assert result is False
                mock_logger.warning.assert_called_once()
                assert "already exists" in mock_logger.warning.call_args[0][0]
    
    def test_run_single_index_file_exists_with_overwrite(self):
        """Test overwriting when output file exists and overwrite is True."""
        mock_result = Mock()
        mock_result.model_dump_json.return_value = '{"log_types": {}}'
        mock_result.log_types = {"type1": {}}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            output_file = output_dir / "test_index_schema.json"
            output_file.write_text('{"existing": "data"}')
            
            with patch('run_schema_agent.run_agent', return_value=mock_result):
                with patch('run_schema_agent.logger'):
                    result = run_single_index(
                        index_name="test_index",
                        log_file="/path/to/logs.jsonl",
                        output_dir=output_dir,
                        llm_client=Mock(),
                        overwrite=True
                    )
                    
                    assert result is True
                    assert output_file.exists()
                    content = output_file.read_text()
                    assert "log_types" in content
    
    def test_run_single_index_agent_failure(self):
        """Test handling of agent execution failure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            with patch(
                'run_schema_agent.run_agent',
                side_effect=Exception("Agent failed")
            ):
                with patch('run_schema_agent.logger') as mock_logger:
                    result = run_single_index(
                        index_name="test_index",
                        log_file="/path/to/logs.jsonl",
                        output_dir=output_dir,
                        llm_client=Mock(),
                        overwrite=False
                    )
                    
                    assert result is False
                    mock_logger.error.assert_called()
                    assert "Failed to process" in mock_logger.error.call_args[0][0]


