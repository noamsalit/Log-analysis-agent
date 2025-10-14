import json
import logging
from langchain_core.tools import tool, ToolException

from logs_analysis_agent.schema_models import SchemaDocument

logger = logging.getLogger(__name__)


@tool
def parse_and_validate_schema_document(text: str) -> SchemaDocument:
    """
    Parse model output as JSON and validate against SchemaDocument.

    Raises on failure; caller can catch and handle.
    
    :param text: JSON string to parse and validate
    :return: Validated SchemaDocument instance
    :raises ToolException: If validation fails
    """
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error("Model output is not valid JSON: %s", exc)
        raise ToolException(f"Model output is not valid JSON: {exc}")
    try:
        return SchemaDocument.model_validate(payload)
    except Exception as exc:
        logger.error("Model output failed SchemaDocument validation: %s", exc)
        raise ToolException(f"Model output failed SchemaDocument validation: {exc}")
