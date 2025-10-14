import logging
from pathlib import Path
from typing import List
from langchain_core.tools import ToolException

logger = logging.getLogger(__name__)


def is_path_allowed(path: str, allowed_dirs: List[str]) -> bool:
    try:
        resolved_path = Path(path).resolve()
    except Exception as e:
        raise ToolException(f"Invalid path '{path}': {e}")
    for allowed_dir in allowed_dirs:
        try:
            resolved_allowed = Path(allowed_dir).resolve()
            resolved_path.relative_to(resolved_allowed)
            return True
        except ValueError:
            continue
        except Exception as e:
            logger.warning(f"Error resolving allowed directory '{allowed_dir}': {e}")
            continue
    return False
