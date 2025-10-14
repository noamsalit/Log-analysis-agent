import logging
import io

from enum import Enum
from pydantic import BaseModel, Field, ConfigDict
from typing import Literal

logger = logging.getLogger(__name__)


class HandleType(str, Enum):
    FILE = "file"


class HandleEntry(BaseModel):
    id: str
    type: HandleType


class FileHandleEntry(HandleEntry):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    type: Literal[HandleType.FILE] = HandleType.FILE
    path: str
    lines_read: int = 0
    handle: io.TextIOBase = Field(exclude=True, repr=False)
    

class HandlesRegistry:
    def __init__(self):
        self.id_to_handle = dict()
    
    def add_handle_entry(self, handle_entry: HandleEntry) -> None:
        """
        Add a handle entry to the registry.
        """
        self.id_to_handle[handle_entry.id] = handle_entry

    def get_handle_entry(self, id: str) -> HandleEntry:
        """
        Get a handle entry.
        :param id: The id of the handle entry to get.
        :return: The handle entry.
        """
        if id not in self.id_to_handle:
            logger.error(f"Handle entry with id {id} not found")
            raise ValueError(f"Handle entry with id {id} not found")
        return self.id_to_handle[id]

    def close_and_remove_handle_entry(self, id: str) -> None:
        """
        Close and remove a handle entry.
        :param id: The id of the handle entry to close.
        """
        if id not in self.id_to_handle:
            logger.error(f"Handle entry with id {id} not found")
            raise ValueError(f"Handle entry with id {id} not found")
        self.id_to_handle[id].handle.close()
        del self.id_to_handle[id]
        logger.debug(f"Handle entry with id {id} closed and removed")

    def clear_registry(self) -> None:
        """
        Clear the registry.
        """
        self.id_to_handle.clear()
        logger.debug("Registry cleared")
