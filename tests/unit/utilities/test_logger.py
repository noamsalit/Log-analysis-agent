import pytest
import logging

from utilities.logger import LogLevel, TRACE


class TestLogLevel:
    """Test LogLevel enum functionality."""
    
    @pytest.mark.parametrize("level_name,expected_value", [
        pytest.param("TRACE", TRACE, id="trace_level"),
        pytest.param("DEBUG", logging.DEBUG, id="debug_level"),
        pytest.param("INFO", logging.INFO, id="info_level"),
        pytest.param("WARNING", logging.WARNING, id="warning_level"),
        pytest.param("ERROR", logging.ERROR, id="error_level"),
    ])
    def test_log_level_values(self, level_name, expected_value):
        """Test LogLevel enum has correct values."""
        level = LogLevel[level_name]
        assert level.value == expected_value
    
    @pytest.mark.parametrize("input_str,expected_level", [
        pytest.param("TRACE", LogLevel.TRACE, id="uppercase_trace"),
        pytest.param("trace", LogLevel.TRACE, id="lowercase_trace"),
        pytest.param("TrAcE", LogLevel.TRACE, id="mixed_case_trace"),
        pytest.param("DEBUG", LogLevel.DEBUG, id="uppercase_debug"),
        pytest.param("info", LogLevel.INFO, id="lowercase_info"),
        pytest.param("WARNING", LogLevel.WARNING, id="uppercase_warning"),
        pytest.param("error", LogLevel.ERROR, id="lowercase_error"),
    ])
    def test_from_string_success_cases(self, input_str, expected_level):
        """Test from_string converts strings to LogLevel correctly."""
        result = LogLevel.from_string(input_str)
        assert result == expected_level
        assert isinstance(result, LogLevel)
    
    @pytest.mark.parametrize("invalid_str", [
        pytest.param("INVALID", id="invalid_level"),
        pytest.param("", id="empty_string"),
        pytest.param("debug_level", id="invalid_format"),
        pytest.param("CRITICAL", id="unsupported_level"),
    ])
    def test_from_string_error_cases(self, invalid_str):
        """Test from_string raises ValueError for invalid input."""
        with pytest.raises(ValueError, match="Invalid log level"):
            LogLevel.from_string(invalid_str)
