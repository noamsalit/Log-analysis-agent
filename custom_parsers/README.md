# Custom Parsers Directory

This directory is used by the Log Analysis Agent to store custom parser functions for log formats that are not supported by the built-in parsers (json_parser, cef_parser, syslog_kv_parser).

## Purpose

When the agent encounters log data in an unknown or unsupported format, it can:
1. Analyze the format
2. Write a custom parser function
3. Save it here for immediate use
4. Create tests in `tests/custom_parsers/`

## Security

This directory is one of the few locations where the agent has write access. The agent's file operations are restricted for security:
- **Read access**: Entire repository
- **Write access**: Only `custom_parsers/` and `tests/custom_parsers/`
- **Execute access**: Only whitelisted commands (pytest, python, black, ruff)

## Usage

Custom parsers should follow this pattern:

```python
from typing import Dict, Any
from langchain_core.tools import tool, ToolException

@tool
def custom_format_parser(data: str) -> Dict[str, Any]:
    """
    Parse custom log format into a structured dictionary.
    
    :param data: Raw log data string
    :return: Parsed data as dictionary
    """
    try:
        # Parsing logic here
        parsed = {}
        # ... implementation ...
        return parsed
    except Exception as e:
        raise ToolException(f"Parsing error: {e}")
```

## Best Practices

1. **Always validate syntax** before saving using `validate_python_syntax`
2. **Write tests** in `tests/custom_parsers/`
3. **Use descriptive names** that indicate the format being parsed
4. **Document the format** in the docstring with examples
5. **Handle errors gracefully** using ToolException

## Files Created

This directory will be populated automatically by the agent during log analysis runs when encountering unsupported formats.

