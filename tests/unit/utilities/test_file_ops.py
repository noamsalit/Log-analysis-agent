import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from langchain_core.tools import ToolException

from utilities.tools.file_ops import (
    search_files,
    find_similar_files,
    read_file_content,
    write_file_content,
    list_directory_contents,
    line_count,
    write_json,
    make_file_tools,
)
from config import (
    ALLOWED_READ_DIRS,
    ALLOWED_WRITE_DIRS,
    ALLOWED_SEARCH_DIRS,
)
from utilities.handles_registry import HandlesRegistry


@pytest.fixture
def temp_test_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_allowed_dirs(temp_test_dir, monkeypatch):
    """Mock the allowed directories to use temp directory."""
    temp_str = str(temp_test_dir)
    
    import utilities.tools.file_ops as file_ops
    
    monkeypatch.setattr(file_ops, 'ALLOWED_READ_DIRS', [temp_str])
    monkeypatch.setattr(file_ops, 'ALLOWED_WRITE_DIRS', [temp_str])
    monkeypatch.setattr(file_ops, 'ALLOWED_SEARCH_DIRS', [temp_str])
    
    yield temp_test_dir


@pytest.fixture(autouse=True)
def sample_files(mock_allowed_dirs):
    """Create sample files for testing. Runs automatically for all tests using mock_allowed_dirs."""
    files = {
        'device_data_amsys.jsonl': '{"log": "data1"}\n{"log": "data2"}',
        'device_data_cnx.jsonl': '{"log": "data3"}',
        'network_data_amsys.json': '{"network": "info"}',
        'test_parser.py': 'def parse(data):\n    return data',
        'subdir/nested_file.txt': 'nested content',
    }
    
    for file_path, content in files.items():
        full_path = mock_allowed_dirs / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
    
    return files


@pytest.mark.parametrize("pattern,expected_count,expected_names", [
    pytest.param("*.jsonl", 2, ["device_data_amsys.jsonl", "device_data_cnx.jsonl"], id="jsonl_extension"),
    pytest.param("device_*.jsonl", 2, ["device_data_amsys.jsonl", "device_data_cnx.jsonl"], id="prefix_pattern"),
    pytest.param("*_amsys.*", 2, ["device_data_amsys.jsonl", "network_data_amsys.json"], id="suffix_pattern"),
    pytest.param("*.py", 1, ["test_parser.py"], id="python_files"),
    pytest.param("subdir/*.txt", 1, ["nested_file.txt"], id="nested_directory"),
    pytest.param("nonexistent_*.file", 0, [], id="no_matches"),
    pytest.param("*.*", 5, None, id="all_files"),
])
def test_search_files_scenarios(pattern, expected_count, expected_names, mock_allowed_dirs):
    """Test file search with various patterns."""
    result = search_files.func(
        pattern=pattern,
        search_dirs=[str(mock_allowed_dirs)]
    )
    
    assert len(result) == expected_count
    
    if expected_names:
        result_names = [Path(p).name for p in result]
        for name in expected_names:
            assert name in result_names


def test_search_files_max_results(mock_allowed_dirs):
    """Test that max_results parameter limits returned files."""
    result = search_files.func(
        pattern="*.*",
        max_results=2,
        search_dirs=[str(mock_allowed_dirs)]
    )
    assert len(result) == 2


def test_search_files_invalid_directory():
    """Test search with directory outside allowed list."""
    with pytest.raises(ToolException, match="No valid search directories"):
        search_files.func(
            pattern="*.txt",
            search_dirs=["/forbidden/path"]
        )


def test_search_files_directory_handling_none():
    """Test search with None search_dirs uses defaults."""
    result = search_files.func(
        pattern="*.txt",
        search_dirs=None
    )
    assert isinstance(result, list)


def test_search_files_directory_handling_invalid():
    """Test search with invalid directory raises exception."""
    with pytest.raises(ToolException, match="No valid search directories"):
        search_files.func(
            pattern="*.txt",
            search_dirs=["/nonexistent/path"]
        )


@pytest.mark.parametrize("filename,threshold,min_expected,should_find", [
    pytest.param("device_data_amsys.jsonl", 90.0, 1, "device_data_amsys.jsonl", id="exact_match"),
    pytest.param("device_dta_amsys", 60.0, 1, "device_data_amsys.jsonl", id="typo_in_word"),
    pytest.param("devce_data", 50.0, 1, "device_data", id="missing_letter"),
    pytest.param("network", 50.0, 1, "network_data_amsys.json", id="partial_name"),
    pytest.param("zzz_nonexistent_xyz", 70.0, 0, None, id="no_similar_files"),
    pytest.param("device", 30.0, 2, "device_data", id="low_threshold_multiple_matches"),
])
def test_find_similar_files_scenarios(
    filename, threshold, min_expected, should_find, mock_allowed_dirs
):
    """Test fuzzy file matching with various scenarios."""
    try:
        result = find_similar_files.func(
            filename=filename,
            threshold=threshold,
            search_dirs=[str(mock_allowed_dirs)]
        )
        
        assert len(result) >= min_expected
        
        if should_find:
            found_names = [Path(r["path"]).name for r in result]
            assert any(
                should_find in name for name in found_names
            )
            
            # Verify structure
            for item in result:
                assert "path" in item
                assert "similarity_score" in item
                assert isinstance(item["similarity_score"], (int, float))
    
    except ToolException as e:
        if "rapidfuzz" in str(e):
            pytest.skip("rapidfuzz library not installed")
        raise


def test_find_similar_files_sorted_by_score(mock_allowed_dirs):
    """Test that results are sorted by similarity score (highest first)."""
    try:
        result = find_similar_files.func(
            filename="device_data",
            threshold=50.0,
            search_dirs=[str(mock_allowed_dirs)]
        )
        
        if len(result) > 1:
            scores = [r["similarity_score"] for r in result]
            assert scores == sorted(scores, reverse=True), "Results not sorted by score"
    
    except ToolException as e:
        if "rapidfuzz" in str(e):
            pytest.skip("rapidfuzz library not installed")
        raise


def test_find_similar_files_max_results(mock_allowed_dirs):
    """Test that max_results parameter limits returned files."""
    try:
        result = find_similar_files.func(
            filename="data",
            threshold=30.0,
            max_results=2,
            search_dirs=[str(mock_allowed_dirs)]
        )
        assert len(result) <= 2
    
    except ToolException as e:
        if "rapidfuzz" in str(e):
            pytest.skip("rapidfuzz library not installed")
        raise


@pytest.mark.parametrize("filename,max_lines,expected_content", [
    pytest.param("device_data_amsys.jsonl", None, '{"log": "data1"}\n{"log": "data2"}', id="full_file"),
    pytest.param("device_data_amsys.jsonl", 1, '{"log": "data1"}\n', id="limited_lines"),
    pytest.param("test_parser.py", None, 'def parse(data):\n    return data', id="python_file"),
    pytest.param("subdir/nested_file.txt", None, 'nested content', id="nested_file"),
])
def test_read_file_content_success_cases(
    filename, max_lines, expected_content, mock_allowed_dirs
):
    """Test reading file content with various configurations."""
    file_path = str(mock_allowed_dirs / filename)
    
    result = read_file_content.func(
        file_path=file_path,
        max_lines=max_lines
    )
    
    if max_lines:
        assert result.startswith(expected_content.split('\n')[0])
    else:
        assert result == expected_content


@pytest.mark.parametrize("file_path,error_match", [
    pytest.param("/forbidden/path/file.txt", "not in allowed directories", id="forbidden_directory"),
    pytest.param("nonexistent.txt", "File not found", id="nonexistent_file"),
])
def test_read_file_content_error_cases(file_path, error_match, mock_allowed_dirs):
    """Test read_file_content error handling."""
    # Adjust path for relative paths
    if not file_path.startswith("/forbidden"):
        file_path = str(mock_allowed_dirs / file_path)
    
    with pytest.raises(ToolException, match=error_match):
        read_file_content.func(file_path=file_path)


def test_read_file_content_directory_not_file(mock_allowed_dirs):
    """Test reading a directory instead of a file."""
    dir_path = mock_allowed_dirs / "subdir"
    
    with pytest.raises(ToolException, match="not a file"):
        read_file_content.func(file_path=str(dir_path))


@pytest.mark.parametrize("filename,content,overwrite", [
    pytest.param("new_parser.py", "def new_parse():\n    pass", False, id="new_file"),
    pytest.param("nested/deep/file.py", "# nested", False, id="create_nested_dirs"),
    pytest.param("test.txt", "content", False, id="simple_write"),
])
def test_write_file_content_success_cases(
    filename, content, overwrite, mock_allowed_dirs
):
    """Test writing file content with various configurations."""
    file_path = str(mock_allowed_dirs / filename)
    
    result = write_file_content.func(
        file_path=file_path,
        content=content,
        overwrite=overwrite
    )
    
    assert "Successfully wrote" in result
    
    written_file = Path(file_path)
    assert written_file.exists()
    assert written_file.read_text() == content


def test_write_file_content_overwrite(mock_allowed_dirs):
    """Test overwriting an existing file."""
    file_path = str(mock_allowed_dirs / "existing.txt")
    
    # Create initial file
    write_file_content.func(
        file_path=file_path,
        content="original",
        overwrite=False
    )
    
    # Try to write without overwrite - should fail
    with pytest.raises(ToolException, match="already exists"):
        write_file_content.func(
            file_path=file_path,
            content="new",
            overwrite=False
        )
    
    # Write with overwrite - should succeed
    write_file_content.func(
        file_path=file_path,
        content="new",
        overwrite=True
    )
    
    assert Path(file_path).read_text() == "new"


def test_write_file_content_forbidden_directory(mock_allowed_dirs):
    """Test writing to forbidden directory."""
    forbidden_path = "/forbidden/path/file.txt"
    
    with pytest.raises(ToolException, match="not in allowed write directories"):
        write_file_content.func(
            file_path=forbidden_path,
            content="content"
        )


@pytest.mark.parametrize("subdir,pattern,files_only,min_expected", [
    pytest.param("", None, False, 4, id="root_all_items"),
    pytest.param("", "*.jsonl", True, 2, id="jsonl_files_only"),
    pytest.param("", "device_*", True, 2, id="pattern_match"),
    pytest.param("subdir", None, True, 1, id="nested_directory"),
    pytest.param("", "*.xyz", True, 0, id="no_matches"),
])
def test_list_directory_contents_scenarios(
    subdir, pattern, files_only, min_expected, mock_allowed_dirs
):
    """Test directory listing with various configurations."""
    dir_path = str(mock_allowed_dirs / subdir) if subdir else str(mock_allowed_dirs)
    
    result = list_directory_contents.func(
        directory_path=dir_path,
        pattern=pattern,
        files_only=files_only
    )
    
    assert len(result) >= min_expected
    assert isinstance(result, list)
    
    if files_only:
        for path in result:
            assert Path(path).is_file()


def test_list_directory_contents_sorted(mock_allowed_dirs):
    """Test that results are sorted alphabetically."""
    result = list_directory_contents.func(
        directory_path=str(mock_allowed_dirs),
        pattern="*.jsonl",
        files_only=True
    )
    
    names = [Path(p).name for p in result]
    assert names == sorted(names), "Results not sorted"


@pytest.mark.parametrize("dir_path,error_match", [
    pytest.param("/forbidden/path", "not in allowed directories", id="forbidden_directory"),
    pytest.param("nonexistent", "not found", id="nonexistent_directory"),
])
def test_list_directory_contents_error_cases(
    dir_path, error_match, mock_allowed_dirs
):
    """Test list_directory_contents error handling."""
    # Adjust path for relative paths
    if not dir_path.startswith("/forbidden"):
        dir_path = str(mock_allowed_dirs / dir_path)
    
    with pytest.raises(ToolException, match=error_match):
        list_directory_contents.func(directory_path=dir_path)


def test_list_directory_contents_file_not_directory(mock_allowed_dirs):
    """Test listing a file instead of directory."""
    file_path = str(mock_allowed_dirs / "device_data_amsys.jsonl")
    
    with pytest.raises(ToolException, match="not a directory"):
        list_directory_contents.func(directory_path=file_path)


class TestLineCount:
    """Test suite for line_count tool."""

    @pytest.mark.parametrize(
        "content,expected_count",
        [
            ("", 0),
            ("single line", 1),
            ("line 1\nline 2\nline 3\n", 3),
            ("line 1\nline 2\nline 3", 3),
        ]
    )
    def test_line_count_success_cases(self, tmp_path, content, expected_count):
        """Test line_count with various file contents."""
        file_path = tmp_path / "test.txt"
        file_path.write_text(content)
        result = line_count.func(str(file_path))
        assert result == expected_count

    def test_line_count_nonexistent_file(self, tmp_path):
        """Test line_count raises error for non-existent file."""
        file_path = tmp_path / "nonexistent.txt"
        with pytest.raises(ToolException, match="Error counting lines"):
            line_count.func(str(file_path))


class TestWriteJson:
    """Test suite for write_json tool."""

    @pytest.mark.parametrize(
        "json_data",
        [
            '{"key": "value"}',
            '{"user": {"name": "John"}, "items": [1, 2, 3]}',
            '{}',
        ]
    )
    def test_write_json_success_cases(self, tmp_path, json_data):
        """Test writing various JSON structures."""
        output_file = tmp_path / "output.json"
        write_json.func(json_data, str(output_file))
        
        assert output_file.exists()
        content = output_file.read_text()
        assert content == json_data

    def test_write_json_invalid_path(self):
        """Test write_json raises error for invalid path."""
        invalid_path = "/nonexistent/directory/file.json"
        with pytest.raises(ToolException, match="Error writing JSON data"):
            write_json.func('{"test": "data"}', invalid_path)


class TestFileTools:
    """Test suite for file tools (open, read, close) that use HandlesRegistry."""

    @pytest.fixture
    def registry(self):
        """Create a fresh HandlesRegistry for each test."""
        return HandlesRegistry()

    @pytest.fixture
    def tools(self, registry):
        """Create file tools with registry."""
        return make_file_tools(registry)

    @pytest.fixture
    def sample_jsonl_file(self, tmp_path):
        """Create a sample JSONL file for testing."""
        file_path = tmp_path / "sample.jsonl"
        lines = [
            '{"id": 1, "name": "Alice"}\n',
            '{"id": 2, "name": "Bob"}\n',
            '{"id": 3, "name": "Charlie"}\n',
            '{"id": 4, "name": "David"}\n',
            '{"id": 5, "name": "Eve"}\n'
        ]
        file_path.write_text("".join(lines))
        return file_path

    def test_open_and_register_jsonl_success(self, tools, sample_jsonl_file):
        """Test successfully opening and registering a JSONL file."""
        open_tool, _, _ = tools
        result = open_tool.func(str(sample_jsonl_file))
        
        assert "Handle entry id:" in result
        assert len(result.split(": ")[1]) == 32

    @pytest.mark.parametrize(
        "file_setup,error_pattern",
        [
            (("nonexistent.jsonl", None), "File not found"),
            (("file.txt", "data"), "not .jsonl"),
        ]
    )
    def test_open_and_register_jsonl_error_cases(self, tools, tmp_path, file_setup, error_pattern):
        """Test errors when opening invalid files."""
        open_tool, _, _ = tools
        filename, content = file_setup
        file_path = tmp_path / filename
        
        if content:
            file_path.write_text(content)
        
        with pytest.raises(ToolException, match=error_pattern):
            open_tool.func(str(file_path))

    @pytest.mark.parametrize(
        "num_lines,expected_lines",
        [
            (2, 2),
            (3, 3),
            (100, 5),
        ]
    )
    def test_read_jsonl_success_cases(self, tools, sample_jsonl_file, num_lines, expected_lines):
        """Test reading various numbers of lines from JSONL file."""
        open_tool, read_tool, _ = tools
        
        result = open_tool.func(str(sample_jsonl_file))
        handle_id = result.split(": ")[1]
        
        data = read_tool.func(handle_id, num_lines)
        lines = json.loads(data)
        assert len(lines) == expected_lines

    def test_read_jsonl_multiple_reads(self, tools, sample_jsonl_file):
        """Test reading multiple times advances the file position."""
        open_tool, read_tool, _ = tools
        
        result = open_tool.func(str(sample_jsonl_file))
        handle_id = result.split(": ")[1]
        
        data1 = read_tool.func(handle_id, 2)
        lines1 = json.loads(data1)
        assert len(lines1) == 2
        
        data2 = read_tool.func(handle_id, 2)
        lines2 = json.loads(data2)
        assert len(lines2) == 2
        assert lines1 != lines2

    def test_read_jsonl_invalid_handle(self, tools):
        """Test error when reading with invalid handle ID."""
        _, read_tool, _ = tools
        
        with pytest.raises(ToolException, match="Invalid or expired handle"):
            read_tool.func("invalid-handle-id", 10)

    def test_close_jsonl_success(self, tools, sample_jsonl_file):
        """Test successfully closing and removing a file handle."""
        open_tool, _, close_tool = tools
        
        result = open_tool.func(str(sample_jsonl_file))
        handle_id = result.split(": ")[1]
        
        close_result = close_tool.func(handle_id)
        assert handle_id in close_result
        assert "closed and removed" in close_result

    @pytest.mark.parametrize(
        "handle_setup",
        [
            "invalid-handle-id",
            "double-close",
        ]
    )
    def test_close_jsonl_error_cases(self, tools, sample_jsonl_file, handle_setup):
        """Test errors when closing invalid or already closed handles."""
        open_tool, _, close_tool = tools
        
        if handle_setup == "double-close":
            result = open_tool.func(str(sample_jsonl_file))
            handle_id = result.split(": ")[1]
            close_tool.func(handle_id)
        else:
            handle_id = handle_setup
        
        with pytest.raises(ToolException, match="Error closing handle"):
            close_tool.func(handle_id)

