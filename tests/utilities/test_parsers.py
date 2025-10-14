import pytest
from langchain_core.tools.base import ToolException

from utilities.tools.parsers import (
    json_parser,
    cef_parser,
    syslog_kv_parser,
    CEFHeaderField
)


class TestJsonParser:
    """Test suite for json_parser function."""

    @pytest.mark.parametrize(
        "message_raw,expected_result",
        [
            # Simple dictionary with single key-value pair
            (
                '{"key": "value"}',
                {"key": "value"}
            ),
            # Nested structure with multiple levels
            (
                '{"user": {"name": "John", "age": 30}}',
                {"user": {"name": "John", "age": 30}}
            ),
            # AWS CloudTrail log format with nested identity object
            (
                '{"eventVersion": "1.08", "userIdentity": {"type": "AssumedRole"}, "eventName": "GetObject"}',
                {"eventVersion": "1.08", "userIdentity": {"type": "AssumedRole"}, "eventName": "GetObject"}
            ),
            # Office 365 audit log format
            (
                '{"CreationTime": "2025-09-21T00:14:59", "Operation": "MessageReadReceiptReceived", "Workload": "MicrosoftTeams"}',
                {"CreationTime": "2025-09-21T00:14:59", "Operation": "MessageReadReceiptReceived", "Workload": "MicrosoftTeams"}
            ),
            # Empty dictionary
            (
                '{}',
                {}
            ),
            # Dictionary with array values
            (
                '{"items": [1, 2, 3], "name": "test"}',
                {"items": [1, 2, 3], "name": "test"}
            ),
        ]
    )
    def test_json_parser_success_cases(self, message_raw, expected_result):
        """Test json_parser with various valid JSON formats."""
        result = json_parser.func(message_raw)
        assert result == expected_result

    @pytest.mark.parametrize(
        "message_raw,expected_result",
        [
            # Leading whitespace should be stripped
            (
                '  {"key": "value"}',
                {"key": "value"}
            ),
            # Trailing whitespace should be stripped
            (
                '{"key": "value"}  ',
                {"key": "value"}
            ),
            # Both leading and trailing whitespace
            (
                '  {"key": "value"}  ',
                {"key": "value"}
            ),
            # Newlines and indentation in JSON
            (
                '{\n  "key": "value"\n}',
                {"key": "value"}
            ),
        ]
    )
    def test_json_parser_edge_cases(self, message_raw, expected_result):
        """Test json_parser handles whitespace and formatting."""
        result = json_parser.func(message_raw)
        assert result == expected_result

    @pytest.mark.parametrize(
        "message_raw,error_pattern",
        [
            # Invalid JSON syntax - missing closing brace
            (
                '{"key": "value"',
                "Invalid JSON format"
            ),
            # Valid JSON but returns a list not a dict
            (
                '["item1", "item2"]',
                "not a dictionary"
            ),
            # Valid JSON but returns a string not a dict
            (
                '"just a string"',
                "not a dictionary"
            ),
            # Valid JSON but returns a number not a dict
            (
                '42',
                "not a dictionary"
            ),
            # Empty string input
            (
                '',
                "Invalid input"
            ),
            # Only whitespace - becomes empty after strip
            (
                '   ',
                "Invalid input"
            ),
        ]
    )
    def test_json_parser_error_cases(self, message_raw, error_pattern):
        """Test json_parser raises appropriate errors."""
        with pytest.raises(ToolException, match=error_pattern):
            json_parser.func(message_raw)


class TestCefParser:
    """Test suite for cef_parser function."""

    @pytest.mark.parametrize(
        "message_raw,expected_result",
        [
            # Fortigate CEF with no extension fields
            (
                "<189>Sep 21 05:44:42 Host CEF:0|Fortinet|Fortigate|v7.0|001|traffic|3|",
                {
                    "syslog_prefix": "<189>Sep 21 05:44:42 Host",
                    "cef_header": {
                        "version": "0",
                        "device_vendor": "Fortinet",
                        "device_product": "Fortigate",
                        "device_version": "v7.0",
                        "signature_id": "001",
                        "name": "traffic",
                        "severity": "3"
                    },
                    "extension": {}
                }
            ),
            # Fortigate CEF with extension fields
            (
                "<189>Sep 21 05:44:42 Host CEF:0|Fortinet|Fortigate|v7.0|001|traffic|3|src=10.1.1.1 dst=8.8.8.8",
                {
                    "syslog_prefix": "<189>Sep 21 05:44:42 Host",
                    "cef_header": {
                        "version": "0",
                        "device_vendor": "Fortinet",
                        "device_product": "Fortigate",
                        "device_version": "v7.0",
                        "signature_id": "001",
                        "name": "traffic",
                        "severity": "3"
                    },
                    "extension": {
                        "src": "10.1.1.1",
                        "dst": "8.8.8.8"
                    }
                }
            ),
            # ArcSight Logger format
            (
                "<134>May 1 12:00:00 host CEF:0|ArcSight|Logger|1.0|100|Login|5|suser=admin",
                {
                    "syslog_prefix": "<134>May 1 12:00:00 host",
                    "cef_header": {
                        "version": "0",
                        "device_vendor": "ArcSight",
                        "device_product": "Logger",
                        "device_version": "1.0",
                        "signature_id": "100",
                        "name": "Login",
                        "severity": "5"
                    },
                    "extension": {
                        "suser": "admin"
                    }
                }
            ),
            # Multiple extension fields with ports
            (
                "<190>Sep 21 CEF:0|Vendor|Product|1.0|100|Event|1|src=1.1.1.1 dst=2.2.2.2 spt=443 dpt=80",
                {
                    "syslog_prefix": "<190>Sep 21",
                    "cef_header": {
                        "version": "0",
                        "device_vendor": "Vendor",
                        "device_product": "Product",
                        "device_version": "1.0",
                        "signature_id": "100",
                        "name": "Event",
                        "severity": "1"
                    },
                    "extension": {
                        "src": "1.1.1.1",
                        "dst": "2.2.2.2",
                        "spt": "443",
                        "dpt": "80"
                    }
                }
            ),
        ]
    )
    def test_cef_parser_success_cases(self, message_raw, expected_result):
        """Test cef_parser with various valid CEF formats."""
        result = cef_parser.func(message_raw)
        assert result == expected_result

    def test_cef_parser_complete_header_fields(self):
        """Test all CEF header fields are correctly parsed."""
        message_raw = "<189>Sep 21 Host CEF:0|Fortinet|Fortigate|v7.0.17|00020|traffic:forward accept|3|src=10.1.1.1"
        result = cef_parser.func(message_raw)
        cef_header = result["cef_header"]
        assert cef_header[CEFHeaderField.VERSION.value] == "0"
        assert cef_header[CEFHeaderField.DEVICE_VENDOR.value] == "Fortinet"
        assert cef_header[CEFHeaderField.DEVICE_PRODUCT.value] == "Fortigate"
        assert cef_header[CEFHeaderField.DEVICE_VERSION.value] == "v7.0.17"
        assert cef_header[CEFHeaderField.SIGNATURE_ID.value] == "00020"
        assert cef_header[CEFHeaderField.NAME.value] == "traffic:forward accept"
        assert cef_header[CEFHeaderField.SEVERITY.value] == "3"

    @pytest.mark.parametrize(
        "message_raw,expected_extension",
        [
            # Extension value contains spaces
            (
                "<189>Host CEF:0|V|P|1|1|E|1|msg=Hello World test=value",
                {"msg": "Hello World", "test": "value"}
            ),
            # Vendor-specific prefixed keys (Fortigate style)
            (
                "<189>Host CEF:0|V|P|1|1|E|1|FTNTFGTsrc=10.1.1.1 FTNTFGTdst=8.8.8.8",
                {"FTNTFGTsrc": "10.1.1.1", "FTNTFGTdst": "8.8.8.8"}
            ),
            # Numeric values in extension
            (
                "<189>Host CEF:0|V|P|1|1|E|1|spt=443 dpt=80 cnt=100",
                {"spt": "443", "dpt": "80", "cnt": "100"}
            ),
            # Complex value with multiple words followed by another field
            (
                "<189>Host CEF:0|V|P|1|1|E|1|msg=User logged in successfully from=192.168.1.1",
                {"msg": "User logged in successfully", "from": "192.168.1.1"}
            ),
        ]
    )
    def test_cef_parser_edge_cases(self, message_raw, expected_extension):
        """Test cef_parser handles edge cases in extensions."""
        result = cef_parser.func(message_raw)
        assert result["extension"] == expected_extension

    @pytest.mark.parametrize(
        "message_raw,error_pattern",
        [
            # Message without CEF marker
            (
                "<189>Sep 21 05:44:42 Host Some log message",
                "CEF:' marker not found"
            ),
            # CEF header with only 6 fields (missing severity)
            (
                "<189>Host CEF:0|Vendor|Product|Version|ID|Name",
                "expected at least 7 pipe-delimited fields, got 6"
            ),
            # CEF header with only 5 fields
            (
                "<189>Host CEF:0|Vendor|Product|Version|ID",
                "expected at least 7 pipe-delimited fields, got 5"
            ),
            # Empty string input
            (
                '',
                "Invalid input"
            ),
            # Only whitespace input
            (
                '   ',
                "Invalid input"
            ),
        ]
    )
    def test_cef_parser_error_cases(self, message_raw, error_pattern):
        """Test cef_parser raises appropriate errors."""
        with pytest.raises(ToolException, match=error_pattern):
            cef_parser.func(message_raw)

    def test_cef_parser_syslog_prefix_extraction(self):
        """Test syslog prefix is correctly extracted."""
        message_raw = "<189>Sep 21 05:44:42 AIS-BOM-100F CEF:0|V|P|1|1|E|1|"
        result = cef_parser.func(message_raw)
        assert result["syslog_prefix"] == "<189>Sep 21 05:44:42 AIS-BOM-100F"

    def test_cef_parser_empty_extension(self):
        """Test CEF message with no extension fields."""
        message_raw = "<189>Host CEF:0|V|P|1|1|E|1|"
        result = cef_parser.func(message_raw)
        assert result["extension"] == {}

    def test_cef_parser_rejects_extra_pipes(self):
        """Test parser rejects malformed CEF with too many pipes.
        
        CEF format requires exactly 7 pipes (creating 8 fields including extension).
        Extra pipes indicate malformed data that should be rejected.
        """
        message_raw = "<189>Host CEF:0|V|P|1|1|E|1|extra|data|src=1.1.1.1"
        with pytest.raises(ToolException, match="too many pipes"):
            cef_parser.func(message_raw)


class TestCEFHeaderFieldEnum:
    """Test suite for CEFHeaderField enum."""

    def test_enum_values(self):
        """Test all enum values are correctly defined."""
        assert CEFHeaderField.VERSION.value == 'version'
        assert CEFHeaderField.DEVICE_VENDOR.value == 'device_vendor'
        assert CEFHeaderField.DEVICE_PRODUCT.value == 'device_product'
        assert CEFHeaderField.DEVICE_VERSION.value == 'device_version'
        assert CEFHeaderField.SIGNATURE_ID.value == 'signature_id'
        assert CEFHeaderField.NAME.value == 'name'
        assert CEFHeaderField.SEVERITY.value == 'severity'

    def test_enum_count(self):
        """Test enum has exactly 7 fields."""
        assert len(CEFHeaderField) == 7


class TestSyslogKvParser:
    """Test suite for syslog_kv_parser function."""

    @pytest.mark.parametrize(
        "message_raw,expected_result",
        [
            # Simple KV pairs without quotes
            (
                '<189>date=2025-09-21 time=05:44:28 level=notice',
                {
                    'prefix': '<189>',
                    'date': '2025-09-21',
                    'time': '05:44:28',
                    'level': 'notice'
                }
            ),
            # KV pairs with quoted values
            (
                '<189>devname="AIS-BOM-100F" devid="FG100FTK21040961" type="traffic"',
                {
                    'prefix': '<189>',
                    'devname': 'AIS-BOM-100F',
                    'devid': 'FG100FTK21040961',
                    'type': 'traffic'
                }
            ),
            # Real Fortigate log example from analysis
            (
                '<189>date=2025-09-21 time=05:44:28 devname="AIS-BOM-100F" devid="FG100FTK21040961" '
                'eventtime=1758413668381601540 tz="+0530" logid="0000000013" type="traffic" '
                'subtype="forward" level="notice" vd="root" srcip=10.11.30.52 srcport=64237',
                {
                    'prefix': '<189>',
                    'date': '2025-09-21',
                    'time': '05:44:28',
                    'devname': 'AIS-BOM-100F',
                    'devid': 'FG100FTK21040961',
                    'eventtime': '1758413668381601540',
                    'tz': '+0530',
                    'logid': '0000000013',
                    'type': 'traffic',
                    'subtype': 'forward',
                    'level': 'notice',
                    'vd': 'root',
                    'srcip': '10.11.30.52',
                    'srcport': '64237'
                }
            ),
            # Mix of quoted and unquoted values
            (
                '<134>user=admin action="login success" ip=192.168.1.1 port=443',
                {
                    'prefix': '<134>',
                    'user': 'admin',
                    'action': 'login success',
                    'ip': '192.168.1.1',
                    'port': '443'
                }
            ),
            # Quoted value with special characters
            (
                '<189>msg="User logged in from remote location" status=success',
                {
                    'prefix': '<189>',
                    'msg': 'User logged in from remote location',
                    'status': 'success'
                }
            ),
            # Empty quoted value
            (
                '<189>field1=value1 field2="" field3=value3',
                {
                    'prefix': '<189>',
                    'field1': 'value1',
                    'field2': '',
                    'field3': 'value3'
                }
            ),
        ]
    )
    def test_syslog_kv_parser_success_cases(self, message_raw, expected_result):
        """Test syslog_kv_parser with various valid formats."""
        result = syslog_kv_parser.func(message_raw)
        assert result == expected_result

    @pytest.mark.parametrize(
        "message_raw,expected_result",
        [
            # Leading whitespace
            (
                '  <189>key=value',
                {'prefix': '<189>', 'key': 'value'}
            ),
            # Trailing whitespace
            (
                '<189>key=value  ',
                {'prefix': '<189>', 'key': 'value'}
            ),
            # Multiple spaces between pairs
            (
                '<189>key1=value1    key2=value2',
                {'prefix': '<189>', 'key1': 'value1', 'key2': 'value2'}
            ),
        ]
    )
    def test_syslog_kv_parser_edge_cases(self, message_raw, expected_result):
        """Test syslog_kv_parser handles whitespace variations."""
        result = syslog_kv_parser.func(message_raw)
        assert result == expected_result

    @pytest.mark.parametrize(
        "message_raw,error_pattern",
        [
            # Missing priority prefix
            (
                'date=2025-09-21 time=05:44:28',
                "Invalid format.*priority prefix"
            ),
            # Invalid priority format (no closing >)
            (
                '<189date=2025-09-21',
                "Invalid format.*priority prefix"
            ),
            # Empty string
            (
                '',
                "Invalid input"
            ),
            # Only priority, no KV pairs
            (
                '<189>',
                "No key-value pairs found"
            ),
            # Malformed KV pair (no value)
            (
                '<189>key1= key2=value2',
                "Invalid key-value pair"
            ),
        ]
    )
    def test_syslog_kv_parser_error_cases(self, message_raw, error_pattern):
        """Test syslog_kv_parser raises appropriate errors."""
        with pytest.raises(ToolException, match=error_pattern):
            syslog_kv_parser.func(message_raw)

    def test_syslog_kv_parser_preserves_numeric_strings(self):
        """Test that numeric values remain as strings."""
        message_raw = '<189>port=443 count=100 ip=10.1.1.1'
        result = syslog_kv_parser.func(message_raw)
        assert result['port'] == '443'
        assert result['count'] == '100'
        assert result['ip'] == '10.1.1.1'
        assert isinstance(result['port'], str)
        assert isinstance(result['count'], str)

    def test_syslog_kv_parser_handles_equals_in_quoted_value(self):
        """Test quoted values can contain equals signs."""
        message_raw = '<189>query="SELECT * FROM users WHERE id=5" status=ok'
        result = syslog_kv_parser.func(message_raw)
        assert result['query'] == 'SELECT * FROM users WHERE id=5'
        assert result['status'] == 'ok'

