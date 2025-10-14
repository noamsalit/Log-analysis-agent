import json
import logging
from enum import Enum
from typing import Dict, Any
from langchain_core.tools import tool, ToolException

logger = logging.getLogger(__name__)


class CEFHeaderField(str, Enum):
    VERSION = 'version'
    DEVICE_VENDOR = 'device_vendor'
    DEVICE_PRODUCT = 'device_product'
    DEVICE_VERSION = 'device_version'
    SIGNATURE_ID = 'signature_id'
    NAME = 'name'
    SEVERITY = 'severity'


@tool
def json_parser(message_raw: str) -> Dict[str, Any]:
    """
    Parse a JSON-formatted message_raw string into a dictionary.
    
    :param message_raw: JSON string to parse
    :return: Parsed JSON as a dictionary with nested structure preserved
    """
    try:
        message_raw = message_raw.strip()
        
        if not message_raw:
            raise ToolException("Invalid input: message_raw must be a non-empty string")
        
        parsed_data = json.loads(message_raw)
        
        if not isinstance(parsed_data, dict):
            raise ToolException(
                f"Parsed JSON is not a dictionary, got {type(parsed_data).__name__}"
            )
        
        logger.debug(
            f"Successfully parsed JSON with {len(parsed_data)} top-level keys"
        )
        return parsed_data
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}")
        raise ToolException(
            f"Invalid JSON format: {str(e)}. "
            f"Error at line {e.lineno}, column {e.colno}"
        )
    except Exception as e:
        logger.error(f"Unexpected error parsing JSON: {e}")
        raise ToolException(f"Unexpected error during JSON parsing: {str(e)}")


@tool
def cef_parser(message_raw: str) -> Dict[str, Any]:
    """
    Parse a CEF (Common Event Format) message into a structured dictionary.
    
    :param message_raw: CEF-formatted string to parse
    :return: Dictionary with 'syslog_prefix', 'cef_header', and 'extension' keys
    
    Example:
        Input:
            "<189>Sep 21 05:44:42 Host CEF:0|Fortinet|Fortigate|v7.0|001|traffic|3|src=10.1.1.1 dst=8.8.8.8"
        
        Output:
            {
                'syslog_prefix': '<189>Sep 21 05:44:42 Host',
                'cef_header': {
                    'version': '0',
                    'device_vendor': 'Fortinet',
                    'device_product': 'Fortigate',
                    'device_version': 'v7.0',
                    'signature_id': '001',
                    'name': 'traffic',
                    'severity': '3'
                },
                'extension': {
                    'src': '10.1.1.1',
                    'dst': '8.8.8.8'
                }
            }
    """
    try:
        message_raw = message_raw.strip()
        
        if not message_raw:
            raise ToolException("Invalid input: message_raw must be a non-empty string")
        
        cef_start = message_raw.find("CEF:")
        if cef_start == -1:
            raise ToolException("Invalid CEF format: 'CEF:' marker not found")
        syslog_prefix = message_raw[:cef_start].strip()
        cef_portion = message_raw[cef_start + 4:]
        parts = cef_portion.split('|')
        if len(parts) < 7:
            raise ToolException(
                f"Invalid CEF header: expected at least 7 pipe-delimited fields, got {len(parts)}"
            )
        if len(parts) > 8:
            raise ToolException(
                f"Invalid CEF format: too many pipes in header. Expected 7 pipes (8 fields), got {len(parts)} fields. "
                f"If pipes are part of field values, they must be escaped as \\|"
            )
        cef_header = {
            CEFHeaderField.VERSION.value: parts[0],
            CEFHeaderField.DEVICE_VENDOR.value: parts[1],
            CEFHeaderField.DEVICE_PRODUCT.value: parts[2],
            CEFHeaderField.DEVICE_VERSION.value: parts[3],
            CEFHeaderField.SIGNATURE_ID.value: parts[4],
            CEFHeaderField.NAME.value: parts[5],
            CEFHeaderField.SEVERITY.value: parts[6]
        }
        extension_str = '|'.join(parts[7:]) if len(parts) > 7 else ''
        extension = _parse_cef_extension(extension_str)
        result = {
            'syslog_prefix': syslog_prefix,
            'cef_header': cef_header,
            'extension': extension
        }
        logger.debug(
            f"Successfully parsed CEF: vendor={cef_header[CEFHeaderField.DEVICE_VENDOR.value]}, "
            f"product={cef_header[CEFHeaderField.DEVICE_PRODUCT.value]}, "
            f"extension_fields={len(extension)}"
        )
        return result

    except ToolException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error parsing CEF: {e}")
        raise ToolException(f"Unexpected error during CEF parsing: {str(e)}")


def _parse_cef_extension(extension_str: str) -> Dict[str, str]:
    """
    Parse CEF extension key-value pairs.
    
    :param extension_str: The extension portion of a CEF message
    :return: Dictionary of extension key-value pairs
    """
    if not extension_str or not extension_str.strip():
        return {}
    extension = {}
    current_key = None
    current_value = []
    in_value = False
    i = 0
    while i < len(extension_str):
        char = extension_str[i]
        if char == '\\' and i + 1 < len(extension_str):
            if in_value:
                current_value.append(extension_str[i + 1])
            i += 2
            continue
        if char == '=' and not in_value:
            key_str = ''.join(current_value).strip()
            if key_str:
                current_key = key_str
                current_value = []
                in_value = True
            i += 1
            continue
        if char == ' ' and in_value:
            next_equals = extension_str.find('=', i)
            next_space = extension_str.find(' ', i + 1)
            if next_equals != -1 and (next_space == -1 or next_equals < next_space):
                potential_key = extension_str[i + 1:next_equals].strip()
                if potential_key and not any(c in potential_key for c in [' ', '=']):
                    if current_key:
                        extension[current_key] = ''.join(current_value)
                    current_key = None
                    current_value = []
                    in_value = False
                    i += 1
                    continue
        current_value.append(char)
        i += 1
    if current_key and current_value:
        extension[current_key] = ''.join(current_value)
    return extension


@tool
def syslog_kv_parser(message_raw: str) -> Dict[str, str]:
    """
    Parse syslog key-value format messages into a dictionary.
    
    Format: <PRI>key1=value1 key2="quoted value" key3=value3 ...
    
    Handles space-separated key=value pairs with optional quoted values.
    Commonly used by Fortigate, Palo Alto, and other network security devices.
    
    :param message_raw: Syslog KV-formatted string to parse
    :return: Dictionary with 'prefix' key for syslog priority and all KV pairs
    
    Example:
        Input:
            '<189>date=2025-09-21 time=05:44:28 devname="AIS-BOM-100F" type="traffic"'
        
        Output:
            {
                'prefix': '<189>',
                'date': '2025-09-21',
                'time': '05:44:28',
                'devname': 'AIS-BOM-100F',
                'type': 'traffic'
            }
    """
    try:
        message_raw = message_raw.strip()
        if not message_raw:
            raise ToolException("Invalid input: message_raw must be a non-empty string")
        
        prefix, kv_portion = _extract_syslog_prefix(message_raw)
        
        result = {'prefix': prefix}
        index = 0
        
        while index < len(kv_portion):
            while index < len(kv_portion) and kv_portion[index] == ' ':
                index += 1
            
            if index >= len(kv_portion):
                break
            
            key, index = _parse_kv_key(kv_portion, index)
            value, index = _parse_kv_value(kv_portion, index, key)
            result[key] = value
        
        logger.debug(f"Successfully parsed syslog KV: {len(result) - 1} key-value pairs")
        return result
    
    except ToolException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error parsing syslog KV: {e}")
        raise ToolException(f"Unexpected error during syslog KV parsing: {str(e)}")


def _extract_syslog_prefix(message_raw: str) -> tuple[str, str]:
    """Extract syslog priority prefix and return prefix and remaining content."""
    if not message_raw.startswith('<'):
        raise ToolException("Invalid format: message must start with syslog priority prefix <PRI>")
    
    prefix_end = message_raw.find('>')
    if prefix_end == -1:
        raise ToolException("Invalid format: missing closing '>' in syslog priority prefix")
    
    prefix = message_raw[:prefix_end + 1]
    kv_portion = message_raw[prefix_end + 1:].strip()
    
    if not kv_portion:
        raise ToolException("No key-value pairs found after priority prefix")
    
    return prefix, kv_portion


def _parse_kv_key(kv_portion: str, index: int) -> tuple[str, int]:
    """Parse a key from KV string and return key and position after '='."""
    key_start = index
    while index < len(kv_portion) and kv_portion[index] != '=':
        index += 1
    
    if index >= len(kv_portion):
        raise ToolException(f"Invalid key-value pair: no '=' found for key starting at position {key_start}")
    
    key = kv_portion[key_start:index].strip()
    if not key:
        raise ToolException("Invalid key-value pair: empty key")
    
    return key, index + 1


def _parse_kv_value(kv_portion: str, index: int, key: str) -> tuple[str, int]:
    """Parse a value (quoted or unquoted) and return value and next position."""
    if index >= len(kv_portion):
        raise ToolException(f"Invalid key-value pair: no value for key '{key}'")
    
    if kv_portion[index] == '"':
        return _parse_quoted_value(kv_portion, index, key)
    else:
        return _parse_unquoted_value(kv_portion, index, key)


def _parse_quoted_value(kv_portion: str, index: int, key: str) -> tuple[str, int]:
    """Parse a quoted value, handling escaped quotes."""
    index += 1
    value_start = index
    while index < len(kv_portion) and kv_portion[index] != '"':
        if kv_portion[index] == '\\' and index + 1 < len(kv_portion):
            index += 2
            continue
        index += 1
    
    if index >= len(kv_portion):
        raise ToolException(f"Invalid key-value pair: unclosed quote for key '{key}'")
    
    value = kv_portion[value_start:index]
    return value, index + 1


def _parse_unquoted_value(kv_portion: str, index: int, key: str) -> tuple[str, int]:
    """Parse an unquoted value (reads until space or end)."""
    value_start = index
    while index < len(kv_portion) and kv_portion[index] != ' ':
        index += 1
    
    value = kv_portion[value_start:index]
    if not value:
        raise ToolException(f"Invalid key-value pair: empty value for key '{key}'")
    
    return value, index
