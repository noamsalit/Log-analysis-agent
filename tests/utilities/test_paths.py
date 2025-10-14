import os
import pytest
from pathlib import Path
from langchain_core.tools import ToolException

from utilities.paths import is_path_allowed


class TestIsPathAllowed:
    """Test suite for the shared is_path_allowed security function."""

    @pytest.mark.parametrize("test_path_rel,allowed_dir_rel,expected", [
        pytest.param("allowed/file.txt", "allowed", True, id="exact_parent_match"),
        pytest.param("allowed/subdir/file.txt", "allowed", True, id="nested_subdirectory"),
        pytest.param("allowed/sub1/sub2/file.txt", "allowed/sub1", True, id="deeper_nesting"),
        pytest.param("allowed", "allowed", True, id="exact_directory_match"),
        pytest.param("allowed/file.txt", "allowed/", True, id="trailing_slash_in_allowed"),
        pytest.param("forbidden/file.txt", "allowed", False, id="different_directory"),
        pytest.param("allowed_other/file.txt", "allowed", False, id="partial_name_match"),
        pytest.param("allowed/../forbidden/file.txt", "allowed", False, id="path_traversal_blocked"),
    ])
    def test_is_path_allowed_scenarios(self, test_path_rel, allowed_dir_rel, expected, tmp_path):
        """Test path validation with various distinct scenarios."""
        allowed_dir = tmp_path / allowed_dir_rel
        allowed_dir.mkdir(parents=True, exist_ok=True)
        
        test_path = tmp_path / test_path_rel
        if test_path != allowed_dir:
            test_path.parent.mkdir(parents=True, exist_ok=True)
            test_path.touch()
        
        result = is_path_allowed(str(test_path), [str(allowed_dir)])
        assert result == expected

    def test_invalid_path_raises_exception(self):
        """Test that invalid paths raise ToolException."""
        with pytest.raises(ToolException, match="Invalid path"):
            is_path_allowed("\x00invalid", ["/tmp"])

    def test_multiple_allowed_directories(self, tmp_path):
        """Test path validation with multiple allowed directories."""
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir3 = tmp_path / "dir3"
        dir1.mkdir()
        dir2.mkdir()
        dir3.mkdir()
        
        file_in_dir1 = dir1 / "test1.txt"
        file_in_dir2 = dir2 / "test2.txt"
        file_in_dir3 = dir3 / "test3.txt"
        file_in_dir1.touch()
        file_in_dir2.touch()
        file_in_dir3.touch()
        
        allowed_dirs = [str(dir1), str(dir2)]
        
        assert is_path_allowed(str(file_in_dir1), allowed_dirs) is True
        assert is_path_allowed(str(file_in_dir2), allowed_dirs) is True
        assert is_path_allowed(str(file_in_dir3), allowed_dirs) is False

    @pytest.mark.parametrize("path_parts,expected", [
        (["a", "b", "c", "d", "e", "file.txt"], True),
        (["deeply", "nested", "structure", "file.txt"], True),
        (["single", "file.txt"], True),
    ])
    def test_deeply_nested_paths(self, path_parts, expected, tmp_path):
        """Test validation with various nesting levels."""
        deep_path = tmp_path.joinpath(*path_parts)
        deep_path.parent.mkdir(parents=True, exist_ok=True)
        deep_path.touch()
        
        result = is_path_allowed(str(deep_path), [str(tmp_path)])
        assert result is expected

    @pytest.mark.parametrize("dir_name,file_name", [
        ("dir-with-dashes", "file.txt"),
        ("dir_with_underscores", "file.txt"),
        ("dir with spaces", "file.txt"),
        ("normal_dir", "file-with-dashes.txt"),
        ("normal_dir", "file with spaces.txt"),
        ("dir-mixed_chars 123", "file-mixed_chars 123.txt"),
    ])
    def test_path_with_special_characters(self, dir_name, file_name, tmp_path):
        """Test paths with special characters (spaces, dashes, underscores)."""
        special_dir = tmp_path / dir_name
        special_dir.mkdir()
        special_file = special_dir / file_name
        special_file.touch()
        
        result = is_path_allowed(str(special_file), [str(tmp_path)])
        assert result is True

    def test_relative_vs_absolute_paths(self, tmp_path):
        """Test that both relative and absolute paths are handled correctly."""
        test_file = tmp_path / "test.txt"
        test_file.touch()
        
        absolute_path = str(test_file.resolve())
        result = is_path_allowed(absolute_path, [str(tmp_path)])
        assert result is True

    def test_nonexistent_path_allowed_dir_exists(self, tmp_path):
        """Test validation of nonexistent file in existing allowed directory."""
        nonexistent = tmp_path / "does_not_exist.txt"
        
        result = is_path_allowed(str(nonexistent), [str(tmp_path)])
        assert result is True

    def test_empty_allowed_dirs_list(self, tmp_path):
        """Test that empty allowed directories list denies all paths."""
        test_path = tmp_path / "test.txt"
        test_path.touch()
        
        result = is_path_allowed(str(test_path), [])
        assert result is False

    @pytest.mark.skipif(os.name == 'nt', reason="Symlinks on Windows require admin privileges")
    @pytest.mark.parametrize("target_in_allowed,expected", [
        (True, True),
        (False, False),
    ])
    def test_symlink_resolution(self, target_in_allowed, expected, tmp_path):
        """Test that symlinks are properly resolved based on their target location."""
        allowed_dir = tmp_path / "allowed"
        forbidden_dir = tmp_path / "forbidden"
        allowed_dir.mkdir()
        forbidden_dir.mkdir()
        
        if target_in_allowed:
            real_dir = allowed_dir / "real"
            real_dir.mkdir()
            symlink_dir = tmp_path / "link"
            symlink_dir.symlink_to(real_dir)
            file_path = symlink_dir / "test.txt"
            file_path.touch()
        else:
            symlink_in_allowed = allowed_dir / "link"
            symlink_in_allowed.symlink_to(forbidden_dir)
            file_path = symlink_in_allowed / "test.txt"
            file_path.touch()
        
        result = is_path_allowed(str(file_path), [str(allowed_dir)])
        assert result is expected

    @pytest.mark.parametrize("traversal_pattern", [
        pytest.param("../forbidden/secret.txt", id="single_parent_traversal"),
        pytest.param("../../forbidden/secret.txt", id="double_parent_traversal"),
        pytest.param("subdir/../../forbidden/secret.txt", id="traversal_from_subdir"),
        pytest.param("./../../forbidden/secret.txt", id="current_then_parent_traversal"),
    ])
    def test_path_traversal_attempts(self, traversal_pattern, tmp_path):
        """Test that various path traversal attempts are properly resolved and blocked."""
        allowed_dir = tmp_path / "sub" / "allowed"
        forbidden_dir = tmp_path / "sub" / "forbidden"
        allowed_dir.mkdir(parents=True)
        forbidden_dir.mkdir(parents=True)
        
        forbidden_file = forbidden_dir / "secret.txt"
        forbidden_file.touch()
        
        traversal_attempt = str(allowed_dir / traversal_pattern)
        result = is_path_allowed(traversal_attempt, [str(allowed_dir)])
        assert result is False

    def test_case_sensitive_paths(self, tmp_path):
        """Test path matching respects filesystem case sensitivity."""
        test_dir = tmp_path / "TestDir"
        test_dir.mkdir()
        test_file = test_dir / "file.txt"
        test_file.touch()
        
        if os.name == 'nt':
            pytest.skip("Windows filesystem is case-insensitive")
        
        result_correct_case = is_path_allowed(str(test_file), [str(test_dir)])
        assert result_correct_case is True

    def test_allowed_dir_with_trailing_slash(self, tmp_path):
        """Test that trailing slashes in allowed dirs don't affect validation."""
        test_file = tmp_path / "test.txt"
        test_file.touch()
        
        allowed_dir_with_slash = str(tmp_path) + "/"
        result = is_path_allowed(str(test_file), [allowed_dir_with_slash])
        assert result is True

    def test_malformed_allowed_directory_logs_warning(self, tmp_path, caplog):
        """Test that malformed allowed directories are handled gracefully."""
        test_file = tmp_path / "test.txt"
        test_file.touch()
        
        invalid_dir = "/nonexistent/\x00/path"
        valid_dir = str(tmp_path)
        
        result = is_path_allowed(str(test_file), [invalid_dir, valid_dir])
        
        assert result is True
        assert "Error resolving allowed directory" in caplog.text or result is True

    def test_root_directory_allowed(self, tmp_path):
        """Test that file in root of allowed directory is accepted."""
        root_file = tmp_path / "root.txt"
        root_file.touch()
        
        result = is_path_allowed(str(root_file), [str(tmp_path)])
        assert result is True

    def test_parent_directory_forbidden(self, tmp_path):
        """Test that parent of allowed directory is forbidden."""
        allowed_subdir = tmp_path / "allowed"
        allowed_subdir.mkdir()
        
        parent_file = tmp_path / "parent.txt"
        parent_file.touch()
        
        result = is_path_allowed(str(parent_file), [str(allowed_subdir)])
        assert result is False
