import pytest
import tempfile
from pathlib import Path
from langchain_core.tools import ToolException

from utilities.tools.code_ops import (
    validate_python_syntax,
    run_safe_command,
)


@pytest.fixture
def temp_test_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_allowed_dirs(temp_test_dir, monkeypatch):
    """Mock the allowed directories to use temp directory."""
    temp_str = str(temp_test_dir)
    
    import utilities.tools.code_ops as code_ops
    
    monkeypatch.setattr(code_ops, 'ALLOWED_READ_DIRS', [temp_str])
    
    yield temp_test_dir


@pytest.mark.parametrize("code,expected_valid", [
    pytest.param("def test():\n    pass", True, id="simple_function"),
    pytest.param("x = 1\ny = 2\nz = x + y", True, id="simple_statements"),
    pytest.param("import json\ndef parse(data):\n    return json.loads(data)", True, id="with_import"),
    pytest.param("class Parser:\n    def __init__(self):\n        pass", True, id="class_definition"),
    pytest.param("", True, id="empty_string"),
    pytest.param("# just a comment", True, id="only_comment"),
    pytest.param("x = 1", True, id="single_line"),
    pytest.param("def test(\n", False, id="unclosed_parenthesis"),
    pytest.param("if True\n    pass", False, id="missing_colon"),
    pytest.param("def test():\npass", False, id="wrong_indentation"),
    pytest.param("x = ", False, id="incomplete_assignment"),
])
def test_validate_python_syntax_scenarios(code, expected_valid):
    """Test Python syntax validation with various code samples."""
    result = validate_python_syntax.func(code=code)
    
    assert isinstance(result, dict)
    assert "valid" in result
    assert "error" in result
    assert "message" in result
    
    assert result["valid"] == expected_valid
    
    if expected_valid:
        assert result["error"] is None
    else:
        assert result["error"] is not None


@pytest.mark.parametrize("command_type,command_args,should_succeed", [
    pytest.param("python", ["--version"], True, id="version_check"),
    pytest.param("pytest", ["--version"], True, id="pytest_version"),
])
def test_run_safe_command_success_cases(
    command_type, command_args, should_succeed, mock_allowed_dirs
):
    """Test safe command execution with allowed commands."""
    try:
        result = run_safe_command.func(
            command_type=command_type,
            command_args=command_args,
            timeout=10,
            working_directory=str(mock_allowed_dirs)
        )
        
        assert isinstance(result, dict), f"Failed scenario: {scenario}"
        assert "success" in result, f"Failed scenario: {scenario}"
        assert "stdout" in result, f"Failed scenario: {scenario}"
        assert "stderr" in result, f"Failed scenario: {scenario}"
        assert "exit_code" in result, f"Failed scenario: {scenario}"
        
        if should_succeed:
            assert result["success"], f"Command failed in scenario: {scenario}"
    
    except ToolException as e:
        if "not available" in str(e).lower():
            pytest.skip(f"{command_type} not available in test environment")
        raise


@pytest.mark.parametrize("command_type,command_args,error_match", [
    pytest.param("rm", ["-rf", "/"], "not allowed", id="forbidden_command"),
    pytest.param("curl", ["http://example.com"], "not allowed", id="network_command"),
    pytest.param("sudo", ["apt-get", "install"], "not allowed", id="privilege_escalation"),
    pytest.param("python", ["-c", "print('hello')"], "Forbidden pattern", id="python_dash_c_blocked"),
    pytest.param("python", ["-c", "os.system('rm -rf /')"], "Forbidden pattern", id="python_dangerous_code"),
])
def test_run_safe_command_error_cases(command_type, command_args, error_match):
    """Test safe command execution blocks dangerous operations."""
    with pytest.raises(ToolException, match=error_match):
        run_safe_command.func(
            command_type=command_type,
            command_args=command_args
        )


def test_run_safe_command_timeout(mock_allowed_dirs):
    """Test command timeout enforcement."""
    slow_script = mock_allowed_dirs / "slow.py"
    slow_script.write_text("import time; time.sleep(100)")
    
    with pytest.raises(ToolException, match="timed out"):
        run_safe_command.func(
            command_type="python",
            command_args=[str(slow_script)],
            timeout=1,
            working_directory=str(mock_allowed_dirs)
        )


def test_run_safe_command_forbidden_working_directory():
    """Test command execution with forbidden working directory."""
    with pytest.raises(ToolException, match="not allowed"):
        run_safe_command.func(
            command_type="python",
            command_args=["--version"],
            working_directory="/forbidden/path"
        )


def test_run_safe_command_captures_output(mock_allowed_dirs):
    """Test that command output is properly captured."""
    test_script = mock_allowed_dirs / "test_output.py"
    test_script.write_text("print('test output'); import sys; sys.stderr.write('error output')")
    
    result = run_safe_command.func(
        command_type="python",
        command_args=[str(test_script)],
        working_directory=str(mock_allowed_dirs)
    )
    
    assert "test output" in result["stdout"]
    assert "error output" in result["stderr"]


def test_run_safe_command_exit_code(mock_allowed_dirs):
    """Test that exit codes are properly captured."""
    success_script = mock_allowed_dirs / "success.py"
    success_script.write_text("exit(0)")
    
    fail_script = mock_allowed_dirs / "fail.py"
    fail_script.write_text("exit(1)")
    
    result_success = run_safe_command.func(
        command_type="python",
        command_args=[str(success_script)],
        working_directory=str(mock_allowed_dirs)
    )
    assert result_success["exit_code"] == 0
    assert result_success["success"] is True
    
    result_fail = run_safe_command.func(
        command_type="python",
        command_args=[str(fail_script)],
        working_directory=str(mock_allowed_dirs)
    )
    assert result_fail["exit_code"] == 1
    assert result_fail["success"] is False
