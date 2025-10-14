# Custom Parser Tests

This directory contains tests for custom parsers created by the Log Analysis Agent.

## Purpose

Every custom parser created in `custom_parsers/` should have corresponding tests here to ensure correctness.

## Test Structure

Follow the project's TDD guidelines:

```python
import pytest
from custom_parsers.my_parser import custom_format_parser

@pytest.mark.parametrize("input_data,expected_output,scenario", [
    # Success cases
    ("valid input 1", {"key": "value"}, "basic_parse"),
    ("valid input 2", {"key": "value2"}, "alternate_format"),
    
    # Edge cases
    ("", {}, "empty_input"),
    
    # Error cases
    ("invalid##input", None, "malformed_data"),
])
def test_custom_parser_scenarios(input_data, expected_output, scenario):
    """Test custom parser with various inputs."""
    if expected_output is None:
        with pytest.raises(Exception):
            custom_format_parser.invoke({"data": input_data})
    else:
        result = custom_format_parser.invoke({"data": input_data})
        assert result == expected_output, f"Failed: {scenario}"
```

## Running Tests

```bash
# Run all custom parser tests
pytest tests/custom_parsers/ -v

# Run specific test file
pytest tests/custom_parsers/test_my_parser.py -v
```

## Guidelines

1. Use parametrized tests for related scenarios
2. Group tests by: success_cases, edge_cases, error_cases
3. Include descriptive scenario names
4. Test both happy path and error conditions
5. Aim for >80% code coverage

