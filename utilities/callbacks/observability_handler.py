import logging
import time
from typing import Any, Dict, List, Optional

from langchain.callbacks.base import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from langchain_core.agents import AgentAction, AgentFinish

from utilities.callbacks.metrics_models import (
    AgentStartMetrics,
    AgentEndMetrics,
    ToolStartMetrics,
    ToolEndMetrics,
    ToolErrorMetrics,
    AgentIterationMetrics
)
from utilities.callbacks.tokens_counter import TokensCounter
from utilities.callbacks.model_normalizers import LLMResponseNormalizer
from utilities.logger import TRACE


def _extract_data_metadata(data: Any, default_key: str = "data") -> tuple[Dict[str, str], Dict[str, int]]:
    """
    Extract keys and byte counts from data (dict or other).
    
    :param data: Input data to analyze (dict or any other type)
    :param default_key: Key name to use if data is not a dict
    :return: Tuple of (keys_dict, byte_counts_dict)
    """
    if isinstance(data, dict):
        keys_dict = {k: str(v) for k, v in data.items()}
        byte_counts = {k: len(str(v).encode('utf-8')) for k, v in data.items()}
    else:
        keys_dict = {default_key: str(type(data).__name__)}
        byte_counts = {default_key: len(str(data).encode('utf-8')) if data else 0}
    return keys_dict, byte_counts


class ObservabilityCallbackHandler(BaseCallbackHandler):
    
    def __init__(self, logger: logging.Logger, run_id: str, normalizer: LLMResponseNormalizer):
        self.logger = logger
        self.run_id = run_id
        self.normalizer = normalizer
        self.token_counter = TokensCounter()
        self._agent_start_time: Optional[float] = None
        self._llm_start_time: Optional[float] = None
        self._tool_start_times: Dict[str, float] = {}
        self._iteration_count = 0
    
    def on_chain_start(self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs: Any) -> None:
        try:
            self._agent_start_time = time.time()
            input_keys, input_byte_counts = _extract_data_metadata(inputs, default_key="input")
            
            metrics = AgentStartMetrics(
                run_id=self.run_id,
                input_keys=input_keys,
                input_byte_counts=input_byte_counts
            )
            
            self.logger.info(f"agent.start - run_id={self.run_id}, inputs={list(input_keys.keys())}")
            self.logger.debug(f"agent.start - {metrics.model_dump_json()}")
        except Exception as e:
            self.logger.error(f"Error in on_chain_start callback: {e}")
    
    def on_chain_end(self, outputs: Dict[str, Any], **kwargs: Any) -> None:
        try:
            duration_ms = (time.time() - self._agent_start_time) * 1000
            output_keys_dict, output_sizes = _extract_data_metadata(outputs, default_key="output")
            output_keys = list(output_keys_dict.keys())
            
            metrics = AgentEndMetrics(
                run_id=self.run_id,
                status="ok",
                duration_ms=duration_ms,
                output_keys=output_keys,
                output_sizes=output_sizes
            )
            
            self.logger.info(f"agent.end - run_id={self.run_id}, status=ok, duration_ms={duration_ms:.2f}")
            
            token_summary = self.token_counter.get_summary(self.run_id)
            self.logger.info(
                f"agent.tokens_summary - run_id={self.run_id}, "
                f"tokens_successful={token_summary.tokens_successful}, "
                f"tokens_billable_estimate={token_summary.tokens_billable_estimate}"
            )
            
            self.logger.debug(f"agent.end - {metrics.model_dump_json()}")
            self.logger.debug(f"agent.tokens_summary - {token_summary.model_dump_json()}")
        except Exception as e:
            self.logger.error(f"Error in on_chain_end callback: {e}")
    
    def on_chain_error(self, error: Exception, **kwargs: Any) -> None:
        try:
            duration_ms = (time.time() - self._agent_start_time) * 1000
            metrics = AgentEndMetrics(
                run_id=self.run_id,
                status="error",
                duration_ms=duration_ms,
                output_keys=[],
                output_sizes={}
            )
            
            self.logger.error(
                f"agent.end - run_id={self.run_id}, status=error, duration_ms={duration_ms:.2f}, "
                f"error={type(error).__name__}: {str(error)}"
            )
            self.logger.debug(f"agent.end - {metrics.model_dump_json()}")
        except Exception as e:
            self.logger.error(f"Error in on_chain_error callback: {e}")
    
    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any) -> None:
        try:
            self._llm_start_time = time.time()
            metrics = self.normalizer.normalize_start(serialized, prompts, self.run_id)
            self.logger.debug(
                f"llm.start - run_id={self.run_id}, model={metrics.model_name}, "
                f"prompt_bytes={metrics.prompt_bytes}"
            )
            if self.logger.isEnabledFor(TRACE):
                self.logger.trace(f"llm.start - {metrics.model_dump_json()}")
        except Exception as e:
            self.logger.error(f"Error in on_llm_start callback: {e}")
    
    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        try:
            duration_ms = (time.time() - self._llm_start_time) * 1000
            usage_metrics = self.normalizer.normalize_usage(response, self.run_id)
            self.token_counter.add_llm_usage(usage_metrics, success=True)
            end_metrics = self.normalizer.normalize_end(response, self.run_id, duration_ms)
            self.logger.debug(
                f"llm.usage - run_id={self.run_id}, "
                f"prompt_tokens={usage_metrics.tokens_prompt}, "
                f"completion_tokens={usage_metrics.tokens_completion}, "
                f"total_tokens={usage_metrics.total_tokens}"
            )
            self.logger.debug(
                f"llm.end - run_id={self.run_id}, status={end_metrics.status}, "
                f"duration_ms={duration_ms:.2f}"
            )
            if self.logger.isEnabledFor(TRACE):
                self.logger.trace(f"llm.usage - {usage_metrics.model_dump_json()}")
                self.logger.trace(f"llm.end - {end_metrics.model_dump_json()}")
        except Exception as e:
            self.logger.error(f"Error in on_llm_end callback: {e}")
    
    def on_llm_error(self, error: Exception, **kwargs: Any) -> None:
        try:
            metrics = self.normalizer.normalize_error(error, self.run_id)
            
            # Track failed tokens for billing estimate if available
            response = kwargs.get('response')
            if response:
                try:
                    usage_metrics = self.normalizer.normalize_usage(response, self.run_id)
                    self.token_counter.add_llm_usage(usage_metrics, success=False)
                    self.logger.debug(
                        f"llm.error - tracked failed tokens: prompt={usage_metrics.tokens_prompt}"
                    )
                except Exception as usage_error:
                    self.logger.debug(f"Could not extract token usage from failed LLM call: {usage_error}")
            
            self.logger.error(
                f"llm.error - run_id={self.run_id}, error_type={metrics.error_type}, "
                f"error_message={metrics.error_message}"
            )
            self.logger.debug(f"llm.error - {metrics.model_dump_json()}")
        except Exception as e:
            self.logger.error(f"Error in on_llm_error callback: {e}")
    
    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs: Any) -> None:
        try:
            tool_name = serialized.get("name", "unknown")
            run_id_for_tool = kwargs.get("run_id", self.run_id)
            
            self._tool_start_times[str(run_id_for_tool)] = time.time()
            input_bytes = len(input_str.encode('utf-8'))
            
            arguments_passed = None
            arg_keys = []
            
            try:
                import json
                parsed_args = json.loads(input_str) if input_str else {}
                arg_keys = list(parsed_args.keys()) if isinstance(parsed_args, dict) else []
                
                if self.logger.isEnabledFor(TRACE):
                    arguments_passed = parsed_args
            except:
                if self.logger.isEnabledFor(TRACE):
                    arguments_passed = {"input_str": input_str}
            
            metrics = ToolStartMetrics(
                run_id=self.run_id,
                tool_name=tool_name,
                input_bytes=input_bytes,
                arguments_passed=arguments_passed
            )
            
            self.logger.debug(
                f"tool.start - run_id={self.run_id}, tool={tool_name}, "
                f"input_bytes={input_bytes}, arg_keys={arg_keys}"
            )
            
            if self.logger.isEnabledFor(TRACE):
                self.logger.trace(f"tool.start - {metrics.model_dump_json()}")
        except Exception as e:
            self.logger.error(f"Error in on_tool_start callback: {e}")
    
    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        try:
            tool_name = kwargs.get("name", "unknown")
            run_id_for_tool = kwargs.get("run_id", self.run_id)
            
            start_time = self._tool_start_times.pop(str(run_id_for_tool), time.time())
            duration_ms = (time.time() - start_time) * 1000
            output_str = str(output) if not isinstance(output, str) else output
            output_bytes = len(output_str.encode('utf-8'))
            
            metrics = ToolEndMetrics(
                run_id=self.run_id,
                tool_name=tool_name,
                status="ok",
                duration_ms=duration_ms,
                output_bytes=output_bytes,
                result_meta={}
            )
            
            output_preview = output_str[:200] if len(output_str) > 200 else output_str
            self.logger.debug(
                f"tool.end - run_id={self.run_id}, tool={tool_name}, status=ok, "
                f"duration_ms={duration_ms:.2f}, output_bytes={output_bytes}, "
                f"output_preview={output_preview}"
            )
            
            if self.logger.isEnabledFor(TRACE):
                self.logger.trace(
                    f"tool.output - run_id={self.run_id}, tool={tool_name}, output={output_str}"
                )
                self.logger.trace(f"tool.end - {metrics.model_dump_json()}")
        except Exception as e:
            self.logger.error(f"Error in on_tool_end callback: {e}")
    
    def on_tool_error(self, error: Exception, **kwargs: Any) -> None:
        try:
            tool_name = kwargs.get("name", "unknown")
            metrics = ToolErrorMetrics(
                run_id=self.run_id,
                tool_name=tool_name,
                error_type=type(error).__name__,
                error_message=str(error)
            )
            self.logger.error(
                f"tool.error - run_id={self.run_id}, tool={tool_name}, "
                f"error_type={metrics.error_type}, error_message={metrics.error_message}"
            )
            self.logger.debug(f"tool.error - {metrics.model_dump_json()}")
        except Exception as e:
            self.logger.error(f"Error in on_tool_error callback: {e}")
    
    def on_agent_action(self, action: AgentAction, **kwargs: Any) -> None:
        try:
            if not self.logger.isEnabledFor(TRACE):
                return
            self._iteration_count += 1
            action_input_str = str(action.tool_input)
            action_input_summary = action_input_str[:200] if len(action_input_str) > 200 else action_input_str
            metrics = AgentIterationMetrics(
                run_id=self.run_id,
                iteration_number=self._iteration_count,
                action_type="tool_call",
                action_input_summary=action_input_summary,
                observation_summary=""
            )
            self.logger.trace(
                f"agent.iteration - run_id={self.run_id}, iteration={self._iteration_count}, "
                f"action={action.tool}, input_summary={action_input_summary}"
            )
            self.logger.trace(f"agent.iteration - {metrics.model_dump_json()}")
        except Exception as e:
            self.logger.error(f"Error in on_agent_action callback: {e}")
    
    def on_agent_finish(self, finish: AgentFinish, **kwargs: Any) -> None:
        try:
            if not self.logger.isEnabledFor(TRACE):
                return
            self._iteration_count += 1
            output_str = str(finish.return_values)
            output_summary = output_str[:200] if len(output_str) > 200 else output_str
            metrics = AgentIterationMetrics(
                run_id=self.run_id,
                iteration_number=self._iteration_count,
                action_type="finish",
                action_input_summary="",
                observation_summary=output_summary
            )
            self.logger.trace(
                f"agent.iteration - run_id={self.run_id}, iteration={self._iteration_count}, "
                f"action=finish, output_summary={output_summary}"
            )
            self.logger.trace(f"agent.iteration - {metrics.model_dump_json()}")
        except Exception as e:
            self.logger.error(f"Error in on_agent_finish callback: {e}")
