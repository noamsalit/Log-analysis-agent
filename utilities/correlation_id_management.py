import uuid
from contextvars import ContextVar
from typing import Optional

_correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


def generate_correlation_id() -> str:
    """
    Generate a unique correlation ID for an agent run.
    
    :return: A unique correlation ID in the format 'run_<uuid>'
    """
    return f"run_{uuid.uuid4().hex}"

def set_correlation_id(run_id: str) -> None:
    """
    Set the correlation ID for the current context.
    
    :param run_id: The correlation ID to set
    """
    _correlation_id.set(run_id)

def get_correlation_id() -> Optional[str]:
    """
    Get the current correlation ID from the context.
    
    :return: The current correlation ID, or None if not set
    """
    return _correlation_id.get()

def clear_correlation_id() -> None:
    """
    Clear the correlation ID from the current context.
    """
    _correlation_id.set(None)
