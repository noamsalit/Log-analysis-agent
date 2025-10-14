import uuid
from contextvars import ContextVar
from typing import Optional

_correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


def generate_correlation_id() -> str:
    return f"run_{uuid.uuid4().hex}"

def set_correlation_id(run_id: str) -> None:
    _correlation_id.set(run_id)

def get_correlation_id() -> Optional[str]:
    return _correlation_id.get()

def clear_correlation_id() -> None:
    _correlation_id.set(None)
