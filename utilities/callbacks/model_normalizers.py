import logging
from abc import ABC, abstractmethod
from typing import Dict, List

from langchain_core.outputs import LLMResult
from utilities.callbacks.metrics_models import (
    LLMStartMetrics,
    LLMUsageMetrics,
    LLMEndMetrics,
    LLMErrorMetrics
)

logger = logging.getLogger(__name__)


class LLMResponseNormalizer(ABC):
    
    @abstractmethod
    def normalize_start(self, serialized: Dict, prompts: List[str], run_id: str) -> LLMStartMetrics:
        pass
    
    @abstractmethod
    def normalize_usage(self, response: LLMResult, run_id: str) -> LLMUsageMetrics:
        pass
    
    @abstractmethod
    def normalize_end(self, response: LLMResult, run_id: str, duration_ms: float) -> LLMEndMetrics:
        pass
    
    @abstractmethod
    def normalize_error(self, error: Exception, run_id: str) -> LLMErrorMetrics:
        pass


class AzureOpenAINormalizer(LLMResponseNormalizer):
    
    def __init__(self):
        self._structure_logged = False
    
    def normalize_start(self, serialized: Dict, prompts: List[str], run_id: str) -> LLMStartMetrics:
        try:
            model_name = serialized.get('name', 'unknown')
            model_version = serialized.get('kwargs', {}).get('model_version', None)
            prompt_bytes = sum(len(p.encode('utf-8')) for p in prompts)
            return LLMStartMetrics(
                run_id=run_id,
                model_name=model_name,
                model_version=model_version,
                prompt_bytes=prompt_bytes
            )
        except Exception as e:
            logger.warning(f"Failed to normalize Azure start event: {e}. Serialized: {serialized}")
            return LLMStartMetrics(run_id=run_id, model_name='unknown', prompt_bytes=0)
    
    def normalize_usage(self, response: LLMResult, run_id: str) -> LLMUsageMetrics:
        try:
            if not self._structure_logged:
                logger.debug(f"Azure LLM response structure - llm_output: {response.llm_output}")
                if response.generations and response.generations[0]:
                    gen = response.generations[0][0]
                    if hasattr(gen, 'message'):
                        if hasattr(gen.message, 'usage_metadata'):
                            logger.debug(f"Azure LLM usage_metadata: {gen.message.usage_metadata}")
                        if hasattr(gen.message, 'response_metadata'):
                            logger.debug(f"Azure LLM response_metadata: {gen.message.response_metadata}")
                self._structure_logged = True
            
            # Try message.usage_metadata first (LangChain 0.3+ with Azure OpenAI)
            if response.generations and response.generations[0]:
                gen = response.generations[0][0]
                if hasattr(gen, 'message') and hasattr(gen.message, 'usage_metadata'):
                    usage_metadata = gen.message.usage_metadata
                    if isinstance(usage_metadata, dict):
                        return LLMUsageMetrics(
                            run_id=run_id,
                            tokens_prompt=usage_metadata.get('input_tokens', 0),
                            tokens_completion=usage_metadata.get('output_tokens', 0),
                            total_tokens=usage_metadata.get('total_tokens', 0)
                        )
            
            # Try llm_output (some LangChain versions put tokens here)
            if response.llm_output and isinstance(response.llm_output, dict):
                if 'token_usage' in response.llm_output:
                    usage = response.llm_output['token_usage']
                    return LLMUsageMetrics(
                        run_id=run_id,
                        tokens_prompt=usage.get('prompt_tokens', 0),
                        tokens_completion=usage.get('completion_tokens', 0),
                        total_tokens=usage.get('total_tokens', 0)
                    )
            
            # Try message.response_metadata (older LangChain versions)
            if response.generations and response.generations[0]:
                gen = response.generations[0][0]
                if hasattr(gen, 'message') and hasattr(gen.message, 'response_metadata'):
                    metadata = gen.message.response_metadata
                    if isinstance(metadata, dict) and 'token_usage' in metadata:
                        usage = metadata['token_usage']
                        return LLMUsageMetrics(
                            run_id=run_id,
                            tokens_prompt=usage.get('prompt_tokens', 0),
                            tokens_completion=usage.get('completion_tokens', 0),
                            total_tokens=usage.get('total_tokens', 0)
                        )
            
            logger.warning(f"Azure response contains no token_usage")
            return LLMUsageMetrics(run_id=run_id, tokens_prompt=0, tokens_completion=0, total_tokens=0)
        except Exception as e:
            logger.warning(f"Failed to normalize Azure usage: {e}")
            return LLMUsageMetrics(run_id=run_id, tokens_prompt=0, tokens_completion=0, total_tokens=0)
    
    def normalize_end(self, response: LLMResult, run_id: str, duration_ms: float) -> LLMEndMetrics:
        try:
            status = "ok" if response.generations else "error"
            return LLMEndMetrics(run_id=run_id, status=status, duration_ms=duration_ms)
        except Exception as e:
            logger.warning(f"Failed to normalize Azure end event: {e}")
            return LLMEndMetrics(run_id=run_id, status="error", duration_ms=duration_ms)
    
    def normalize_error(self, error: Exception, run_id: str) -> LLMErrorMetrics:
        return LLMErrorMetrics(run_id=run_id, error_type=type(error).__name__, error_message=str(error))

