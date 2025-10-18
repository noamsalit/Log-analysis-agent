import json
import logging
import uuid
from itertools import islice
from pathlib import Path
from typing import List, Dict, Any, Optional, TextIO
from langchain_core.tools import tool, ToolException

from utilities.handles_registry import HandlesRegistry, FileHandleEntry
from config import (
    ALLOWED_READ_DIRS,
    ALLOWED_WRITE_DIRS,
    ALLOWED_SEARCH_DIRS,
)
from utilities.paths import is_path_allowed

logger = logging.getLogger(__name__)


def _validate_search_directories(
    search_dirs: Optional[List[str]], 
    allowed_dirs: List[str]
) -> List[str]:
    if search_dirs is None:
        search_dirs = allowed_dirs
    
    validated_dirs = []
    for dir_path in search_dirs:
        if not is_path_allowed(dir_path, allowed_dirs):
            logger.warning(f"Search directory not allowed: {dir_path}")
            continue
        validated_dirs.append(dir_path)
    
    if not validated_dirs:
        raise ToolException(
            f"No valid search directories provided. Allowed: {allowed_dirs}"
        )
    
    return validated_dirs


def _validate_file_path(file_path: str, allowed_dirs: List[str]) -> Path:
    """
    Validate that a file path exists, is a file, and is within allowed directories.
    
    :param file_path: Path to the file to validate
    :param allowed_dirs: List of allowed directory paths
    :return: Validated Path object
    """
    if not is_path_allowed(file_path, allowed_dirs):
        raise ToolException(
            f"File path not in allowed directories. Allowed: {allowed_dirs}"
        )
    
    path_obj = Path(file_path)
    if not path_obj.exists():
        raise ToolException(f"File not found: {file_path}")
    
    if not path_obj.is_file():
        raise ToolException(f"Path is not a file: {file_path}")
    
    return path_obj


def _validate_directory_path(directory_path: str, allowed_dirs: List[str]) -> Path:
    """
    Validate that a directory path exists, is a directory, and is within allowed directories.
    
    :param directory_path: Path to the directory to validate
    :param allowed_dirs: List of allowed directory paths
    :return: Validated Path object
    """
    if not is_path_allowed(directory_path, allowed_dirs):
        raise ToolException(
            f"Directory not in allowed directories. Allowed: {allowed_dirs}"
        )
    
    dir_obj = Path(directory_path)
    if not dir_obj.exists():
        raise ToolException(f"Directory not found: {directory_path}")
    
    if not dir_obj.is_dir():
        raise ToolException(f"Path is not a directory: {directory_path}")
    
    return dir_obj


@tool
def search_files(
    pattern: str, 
    search_dirs: Optional[List[str]] = None,
    max_results: int = 20
) -> List[str]:
    """
    Search for files matching a glob pattern in specified directories.
    
    :param pattern: Glob pattern to match (e.g., '*.jsonl', 'device_*_flattened.json')
    :param search_dirs: List of directories to search in. If None, searches in all allowed directories.
    :param max_results: Maximum number of results to return
    :return: List of matching file paths
    """
    try:
        validated_dirs = _validate_search_directories(search_dirs, ALLOWED_SEARCH_DIRS)
        
        results = []
        for dir_path in validated_dirs:
            dir_obj = Path(dir_path)
            if not dir_obj.exists():
                logger.warning(f"Directory does not exist: {dir_path}")
                continue
            
            matches = dir_obj.rglob(pattern)
            for match in matches:
                if match.is_file():
                    results.append(str(match))
                    if len(results) >= max_results:
                        break
            
            if len(results) >= max_results:
                break
        
        logger.info(f"Found {len(results)} files matching pattern '{pattern}'")
        return results[:max_results]
    
    except ToolException:
        raise
    except Exception as e:
        logger.error(f"Error searching files: {e}")
        raise ToolException(f"Error searching files: {e}")


@tool
def find_similar_files(
    filename: str,
    search_dirs: Optional[List[str]] = None,
    threshold: float = 70.0,
    max_results: int = 10
) -> List[Dict[str, Any]]:
    """
    Find files with names similar to the input using fuzzy matching.
    Useful for finding files when the exact name is uncertain or contains typos.
    
    :param filename: Filename or partial filename to search for
    :param search_dirs: List of directories to search in. If None, searches in all allowed directories.
    :param threshold: Minimum similarity score (0-100). Default 70.0.
    :param max_results: Maximum number of results to return
    :return: List of dicts with 'path' and 'similarity_score' keys, sorted by score
    """
    try:
        from rapidfuzz import fuzz, process
    except ImportError:
        raise ToolException(
            "rapidfuzz library not installed. Install with: pip install rapidfuzz"
        )
    
    try:
        validated_dirs = _validate_search_directories(search_dirs, ALLOWED_SEARCH_DIRS)
        all_files = _collect_files_from_directories(validated_dirs)
        
        if not all_files:
            logger.warning("No files found in search directories")
            return []
        
        file_names = [Path(f).name for f in all_files]
        matches = process.extract(
            filename,
            file_names,
            scorer=fuzz.WRatio,
            limit=max_results,
            score_cutoff=threshold
        )
        
        results = _map_fuzzy_matches_to_paths(matches, all_files)
        
        logger.info(
            f"Found {len(results)} similar files for '{filename}' "
            f"(threshold: {threshold})"
        )
        return results
    
    except ToolException:
        raise
    except Exception as e:
        logger.error(f"Error in fuzzy file search: {e}")
        raise ToolException(f"Error in fuzzy file search: {e}")


def _collect_files_from_directories(validated_dirs: List[str]) -> List[str]:
    """
    Recursively collect all file paths from the given directories.
    
    :param validated_dirs: List of directory paths to search
    :return: List of absolute file paths as strings
    """
    all_files = []
    for dir_path in validated_dirs:
        dir_obj = Path(dir_path)
        if not dir_obj.exists():
            logger.warning(f"Directory does not exist: {dir_path}")
            continue
        
        for file_path in dir_obj.rglob("*"):
            if file_path.is_file():
                all_files.append(str(file_path))
    
    return all_files


def _map_fuzzy_matches_to_paths(matches, all_files: List[str]) -> List[Dict[str, Any]]:
    """
    Map fuzzy match results (filename, score) back to full file paths.
    
    :param matches: Fuzzy match results from rapidfuzz.process.extract
    :param all_files: List of all file paths to map from
    :return: List of dicts with 'path' and 'similarity_score' keys
    """
    results = []
    for matched_name, score, _ in matches:
        for full_path in all_files:
            if Path(full_path).name == matched_name:
                results.append({
                    "path": full_path,
                    "similarity_score": round(score, 2)
                })
                break
    return results


@tool
def list_directory_contents(
    directory_path: str,
    pattern: Optional[str] = None,
    files_only: bool = False
) -> List[str]:
    """
    List contents of a directory with security restrictions.
    
    :param directory_path: Path to directory to list
    :param pattern: Optional glob pattern to filter results
    :param files_only: If True, return only files (not directories)
    :return: List of paths in the directory
    """
    try:
        dir_obj = _validate_directory_path(directory_path, ALLOWED_READ_DIRS)
        
        if pattern:
            items = dir_obj.glob(pattern)
        else:
            items = dir_obj.iterdir()
        
        results = []
        for item in items:
            if files_only and not item.is_file():
                continue
            results.append(str(item))
        
        results.sort()
        logger.debug(f"Listed {len(results)} items in {directory_path}")
        return results
    
    except ToolException:
        raise
    except Exception as e:
        logger.error(f"Error listing directory {directory_path}: {e}")
        raise ToolException(f"Error listing directory: {e}")


@tool
def read_file_content(file_path: str, max_lines: Optional[int] = None) -> str:
    """
    Read content from a file with security restrictions.
    
    :param file_path: Path to the file to read
    :param max_lines: Optional limit on number of lines to read
    :return: File content as string
    """
    try:
        path_obj = _validate_file_path(file_path, ALLOWED_READ_DIRS)
        
        with open(path_obj, 'r', encoding='utf-8', errors='ignore') as f:
            if max_lines:
                lines = [next(f) for _ in range(max_lines) if f]
                content = ''.join(lines)
            else:
                content = f.read()
        
        logger.debug(f"Read {len(content)} characters from {file_path}")
        return content
    
    except ToolException:
        raise
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        raise ToolException(f"Error reading file: {e}")


@tool
def write_file_content(file_path: str, content: str, overwrite: bool = False) -> str:
    """
    Write content to a file with security restrictions.
    Only allowed in designated directories (custom_parsers, tests/custom_parsers).
    
    :param file_path: Path to the file to write
    :param content: Content to write to the file
    :param overwrite: If True, overwrite existing file. If False, fail if file exists.
    :return: Success message with file path
    """
    try:
        if not is_path_allowed(file_path, ALLOWED_WRITE_DIRS):
            raise ToolException(
                f"File path not in allowed write directories. "
                f"Allowed: {ALLOWED_WRITE_DIRS}"
            )
        
        path_obj = Path(file_path)
        
        if path_obj.exists() and not overwrite:
            raise ToolException(
                f"File already exists: {file_path}. "
                f"Set overwrite=True to replace it."
            )
        
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        path_obj.write_text(content, encoding='utf-8')
        
        logger.info(f"Wrote {len(content)} characters to {file_path}")
        return f"Successfully wrote to {file_path}"
    
    except ToolException:
        raise
    except Exception as e:
        logger.error(f"Error writing file {file_path}: {e}")
        raise ToolException(f"Error writing file: {e}")


@tool
def line_count(path: str) -> int:
    """
    Count the number of lines in a file.

    :param path: The path to the file to count the lines of.
    :return: The number of lines in the file.
    """
    try:
        logger.debug(f"Counting lines in {path}")
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return sum(1 for _ in f)
    except Exception as e:
        logger.error(f"Error counting lines in {path}: {e}")
        raise ToolException(f"Error counting lines in {path}: {e}")


@tool
def write_json(json_data: str, output_file: str) -> None:
    """
    Write the given JSON data to a file.

    :param json_data: The JSON data to write to the file.
    :param output_file: The path to the output file.
    :return: A message indicating the JSON data has been written to the file.
    """
    try:
        with open(output_file, "w") as f:
            f.write(json_data)
            logger.info(f"JSON data written to {output_file}")
    except Exception as e:
        logger.error(f"Error writing JSON data to {output_file}: {e}")
        raise ToolException(f"Error writing JSON data to {output_file}: {e}")


def make_file_tools(registry: HandlesRegistry):
    """
    Create JSONL file operation tools with registry support.
    These tools maintain state for streaming line-by-line reading of large JSONL files.
    
    :param registry: HandlesRegistry instance to manage file handles
    :return: List of tool functions [open_and_register_jsonl, read_jsonl, close_jsonl]
    """
    @tool
    def open_and_register_jsonl(path: str) -> str:
        """
        Open a JSONL file, add the handle entry to the registry and return the handle entry id.

        :param path: The path to the JSONL file to open.
        :return: The handle entry id.
        """
        p = Path(path)
        if not p.exists() or p.suffix.lower() != ".jsonl":
            raise ToolException("File not found or not .jsonl")
        try:
            file_handle = p.open('r', encoding='utf-8', errors='ignore')
        except Exception as e:
            logger.error(f"Error getting file handle for {path}: {e}")
            raise ToolException(f"Error getting file handle for {path}: {e}")
        handle_entry_id = uuid.uuid4().hex
        entry = FileHandleEntry(id=handle_entry_id, path=path, handle=file_handle, lines_read=0)
        try:
            registry.add_handle_entry(entry)
        except ValueError as e:
            raise ToolException(f"Error adding handle entry to registry: {e}")
        return f"Handle entry id: {handle_entry_id}"

    @tool
    def read_jsonl(handle_entry_id: str, number_of_lines: int = 50) -> str:
        """
        Read the given number of lines from a JSONL file from the registry.

        :param handle_entry_id: The handle entry id.
        :param number_of_lines: The number of lines to read.
        :return: The JSONL data.
        """
        if number_of_lines < 1:
            raise ToolException("Number of lines must be greater than 0")
        try:
            entry = registry.get_handle_entry(handle_entry_id)
        except (KeyError, ValueError):
            raise ToolException("Invalid or expired handle")
        handle: TextIO = entry.handle
        data = [line for line in islice(handle, number_of_lines)]
        entry.lines_read += len(data)
        return json.dumps(data, ensure_ascii=False)


    @tool
    def close_jsonl(handle_entry_id: str) -> str:
        """
        Close a JSONL file from the registry.

        :param handle_entry_id: The handle entry id.
        :return: A message indicating the JSONL file has been closed.
        """
        try:
            registry.close_and_remove_handle_entry(handle_entry_id)
            return f"Handle entry id: {handle_entry_id} closed and removed"
        except Exception as e:
            logger.error(f"Error closing handle entry id: {handle_entry_id}: {e}")
            raise ToolException(f"Error closing handle entry id: {handle_entry_id}: {e}")

    return [open_and_register_jsonl, read_jsonl, close_jsonl]
