import ast
import logging
import subprocess
from typing import List, Dict, Any, Optional
from langchain_core.tools import tool, ToolException

from config import ALLOWED_READ_DIRS
from utilities.paths import is_path_allowed

logger = logging.getLogger(__name__)

ALLOWED_COMMANDS = {
    "pytest": {
        "executable": "pytest",
        "description": "Run pytest tests",
        "allowed_args": ["--version", "-v", "--verbose", "-x", "--tb=short", "--tb=long", "-k"],
        "requires_file_arg": True,
        "forbidden_patterns": []
    },
    "python": {
        "executable": "python",
        "description": "Run Python scripts (syntax check, compile)",
        "allowed_args": ["--version", "-m", "py_compile"],
        "requires_file_arg": False,
        "forbidden_patterns": ["-c", "--command", "exec", "eval", "os.system", "subprocess"]
    },
    "black": {
        "executable": "black",
        "description": "Format Python code",
        "allowed_args": ["--version", "--check", "--diff", "--line-length"],
        "requires_file_arg": True,
        "forbidden_patterns": []
    },
    "ruff": {
        "executable": "ruff",
        "description": "Lint Python code",
        "allowed_args": ["--version", "check"],
        "requires_file_arg": False,
        "forbidden_patterns": []
    }
}


def _validate_command_args(command_type: str, args: List[str]) -> None:
    command_info = ALLOWED_COMMANDS[command_type]
    args_str = " ".join(args)
    for pattern in command_info["forbidden_patterns"]:
        if pattern in args_str:
            raise ToolException(
                f"Forbidden pattern '{pattern}' found in arguments for {command_type}"
            )
    for arg in args:
        if arg.endswith(('.py', '.jsonl', '.json', '.txt')) or '/' in arg:
            continue
        if arg.isdigit():
            continue
        if len(args) > 1 and args[args.index(arg) - 1] == "-k":
            continue
        is_allowed = any(
            arg == allowed_arg or arg.startswith(allowed_arg + "=")
            for allowed_arg in command_info["allowed_args"]
        )
        if not is_allowed:
            raise ToolException(
                f"Argument '{arg}' not allowed for {command_type}. "
                f"Allowed: {command_info['allowed_args']}"
            )
    for arg in args:
        if '/' in arg or arg.endswith(('.py', '.jsonl', '.json', '.txt')):
            if not is_path_allowed(arg, ALLOWED_READ_DIRS):
                raise ToolException(
                    f"File path in arguments not allowed: {arg}"
                )


@tool
def validate_python_syntax(code: str) -> Dict[str, Any]:
    """
    Validate Python code syntax without executing it.
    
    :param code: Python code to validate
    :return: Dict with 'valid' (bool), 'error' (str or None), and 'message' (str)
    """
    try:
        ast.parse(code)
        return {
            "valid": True,
            "error": None,
            "message": "Code syntax is valid"
        }
    except SyntaxError as e:
        return {
            "valid": False,
            "error": str(e),
            "message": f"Syntax error at line {e.lineno}: {e.msg}"
        }
    except Exception as e:
        return {
            "valid": False,
            "error": str(e),
            "message": f"Validation error: {str(e)}"
        }


@tool
def run_safe_command(
    command_type: str,
    command_args: List[str],
    timeout: int = 30,
    working_directory: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run a whitelisted command with security restrictions.
    
    :param command_type: Type of command to run (pytest, python, black, ruff)
    :param command_args: List of arguments to pass to the command
    :param timeout: Maximum execution time in seconds (default 30)
    :param working_directory: Directory to run command in (must be in allowed dirs)
    :return: Dict with 'success' (bool), 'stdout' (str), 'stderr' (str), 'exit_code' (int)
    """
    try:
        if command_type not in ALLOWED_COMMANDS:
            raise ToolException(
                f"Command type '{command_type}' not allowed. "
                f"Allowed: {list(ALLOWED_COMMANDS.keys())}"
            )
        command_info = ALLOWED_COMMANDS[command_type]
        executable = command_info["executable"]
        _validate_command_args(command_type, command_args)
        cmd = [executable] + command_args
        if working_directory:
            if not is_path_allowed(working_directory, ALLOWED_READ_DIRS):
                raise ToolException(
                    f"Working directory not allowed: {working_directory}"
                )
            cwd = working_directory
        else:
            cwd = ALLOWED_READ_DIRS[0]
        logger.info(f"Running command: {' '.join(cmd)} in {cwd}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode
        }
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out after {timeout} seconds")
        raise ToolException(f"Command timed out after {timeout} seconds")
    except ToolException:
        raise
    except Exception as e:
        logger.error(f"Error running command: {e}")
        raise ToolException(f"Error running command: {e}")
