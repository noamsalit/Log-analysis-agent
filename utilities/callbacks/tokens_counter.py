from dataclasses import dataclass
from utilities.callbacks.metrics_models import (
    LLMUsageMetrics,
    AgentTokenSummaryMetrics
)


@dataclass
class TokensCounter:
    """
    Mutable state collector for aggregating token usage across an agent run.
    """
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    failed_llm_calls_tokens: int = 0
    
    def add_llm_usage(self, usage: LLMUsageMetrics, success: bool) -> None:
        """
        Accumulate token usage from an LLM call.
        
        :param usage: Token metrics from the LLM call
        :param success: Whether the call was successful (affects billable estimate)
        """
        if success:
            self.total_prompt_tokens += usage.tokens_prompt
            self.total_completion_tokens += usage.tokens_completion
            self.total_tokens += usage.total_tokens
        else:
            self.failed_llm_calls_tokens += usage.tokens_prompt
    
    def get_summary(self, run_id: str) -> AgentTokenSummaryMetrics:
        """
        Generate token summary metrics for the run.
        
        :param run_id: Correlation ID for the agent run
        :return: AgentTokenSummaryMetrics with successful and billable token counts
        """
        return AgentTokenSummaryMetrics(
            run_id=run_id,
            tokens_successful=self.total_tokens,
            tokens_billable_estimate=self.total_tokens + self.failed_llm_calls_tokens
        )
