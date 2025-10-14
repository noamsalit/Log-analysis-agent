import pytest
from utilities.callbacks.tokens_counter import TokensCounter
from utilities.callbacks.metrics_models import (
    LLMUsageMetrics,
    AgentTokenSummaryMetrics
)


class TestTokensCounter:
    """Test token aggregation across LLM calls in an agent run."""
    
    @pytest.mark.parametrize("tokens_prompt,tokens_completion,total_tokens,success,expected_state", [
        pytest.param(100, 50, 150, True, {
            "total_prompt_tokens": 100,
            "total_completion_tokens": 50,
            "total_tokens": 150,
            "failed_llm_calls_tokens": 0
        }, id="success_normal_usage"),
        pytest.param(5000, 2000, 7000, True, {
            "total_prompt_tokens": 5000,
            "total_completion_tokens": 2000,
            "total_tokens": 7000,
            "failed_llm_calls_tokens": 0
        }, id="success_large_usage"),
        pytest.param(100, 0, 100, False, {
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_tokens": 0,
            "failed_llm_calls_tokens": 100
        }, id="failure_prompt_only"),
        pytest.param(500, 0, 500, False, {
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_tokens": 0,
            "failed_llm_calls_tokens": 500
        }, id="failure_large_prompt"),
    ])
    def test_add_llm_usage_success_cases(self, tokens_prompt, tokens_completion, total_tokens, success, expected_state):
        """Test adding LLM usage updates correct counters based on success status."""
        collector = TokensCounter()
        usage = LLMUsageMetrics(
            run_id="run_123",
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion,
            total_tokens=total_tokens
        )
        collector.add_llm_usage(usage, success=success)
        
        assert collector.total_prompt_tokens == expected_state["total_prompt_tokens"]
        assert collector.total_completion_tokens == expected_state["total_completion_tokens"]
        assert collector.total_tokens == expected_state["total_tokens"]
        assert collector.failed_llm_calls_tokens == expected_state["failed_llm_calls_tokens"]
    
    @pytest.mark.parametrize("tokens_prompt,tokens_completion,total_tokens,success", [
        pytest.param(0, 0, 0, True, id="success_zero_tokens"),
        pytest.param(0, 0, 0, False, id="failure_zero_tokens"),
        pytest.param(1, 1, 2, True, id="success_minimal_tokens"),
        pytest.param(1, 0, 1, False, id="failure_minimal_tokens"),
        pytest.param(10000, 5000, 15000, True, id="success_very_large_tokens"),
        pytest.param(10000, 0, 10000, False, id="failure_very_large_tokens"),
    ])
    def test_add_llm_usage_edge_cases(self, tokens_prompt, tokens_completion, total_tokens, success):
        """Test adding LLM usage handles edge cases correctly."""
        collector = TokensCounter()
        usage = LLMUsageMetrics(
            run_id="run_123",
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion,
            total_tokens=total_tokens
        )
        collector.add_llm_usage(usage, success=success)
        
        if success:
            assert collector.total_tokens == total_tokens
            assert collector.failed_llm_calls_tokens == 0
        else:
            assert collector.total_tokens == 0
            assert collector.failed_llm_calls_tokens == tokens_prompt
    
    def test_collector_initialization_state(self):
        """Test collector initializes with all counters at zero."""
        collector = TokensCounter()
        assert collector.total_prompt_tokens == 0
        assert collector.total_completion_tokens == 0
        assert collector.total_tokens == 0
        assert collector.failed_llm_calls_tokens == 0
    
    def test_multiple_failures_accumulate(self):
        """Test multiple failed LLM calls accumulate in failed_llm_calls_tokens."""
        collector = TokensCounter()
        for _ in range(3):
            usage = LLMUsageMetrics(
                run_id="run_123",
                tokens_prompt=50,
                tokens_completion=0,
                total_tokens=50
            )
            collector.add_llm_usage(usage, success=False)
        
        assert collector.total_tokens == 0
        assert collector.failed_llm_calls_tokens == 150
    
    def test_get_summary_returns_pydantic(self):
        """Test get_summary returns AgentTokenSummaryMetrics with correct totals."""
        collector = TokensCounter()
        collector.add_llm_usage(
            LLMUsageMetrics(
                run_id="run_123",
                tokens_prompt=100,
                tokens_completion=50,
                total_tokens=150
            ),
            success=True
        )
        collector.add_llm_usage(
            LLMUsageMetrics(
                run_id="run_123",
                tokens_prompt=75,
                tokens_completion=0,
                total_tokens=75
            ),
            success=False
        )
        summary = collector.get_summary("run_123")
        assert isinstance(summary, AgentTokenSummaryMetrics)
        assert summary.tokens_successful == 150
        assert summary.tokens_billable_estimate == 225
        assert summary.run_id == "run_123"
    
    def test_token_collector_aggregates_multiple_calls(self):
        """Test token collector incrementally aggregates across multiple LLM calls."""
        collector = TokensCounter()
        run_id = "run_test123"
        collector.add_llm_usage(
            LLMUsageMetrics(run_id=run_id, tokens_prompt=100, tokens_completion=50, total_tokens=150),
            success=True
        )
        assert collector.total_tokens == 150
        assert collector.total_prompt_tokens == 100
        assert collector.total_completion_tokens == 50
        assert collector.failed_llm_calls_tokens == 0
        collector.add_llm_usage(
            LLMUsageMetrics(run_id=run_id, tokens_prompt=100, tokens_completion=50, total_tokens=150),
            success=True
        )
        assert collector.total_tokens == 300
        assert collector.total_prompt_tokens == 200
        assert collector.total_completion_tokens == 100
        assert collector.failed_llm_calls_tokens == 0
        collector.add_llm_usage(
            LLMUsageMetrics(run_id=run_id, tokens_prompt=100, tokens_completion=50, total_tokens=150),
            success=True
        )
        assert collector.total_tokens == 450
        assert collector.total_prompt_tokens == 300
        assert collector.total_completion_tokens == 150
        assert collector.failed_llm_calls_tokens == 0
        collector.add_llm_usage(
            LLMUsageMetrics(run_id=run_id, tokens_prompt=75, tokens_completion=0, total_tokens=75),
            success=False
        )
        assert collector.total_tokens == 450 
        assert collector.failed_llm_calls_tokens == 75
        summary = collector.get_summary(run_id)
        assert summary.tokens_successful == 450
        assert summary.tokens_billable_estimate == 525
    
    def test_mixed_success_and_failure_calls(self):
        """Test collector handles mixed successful and failed calls correctly."""
        collector = TokensCounter()
        for _ in range(2):
            collector.add_llm_usage(
                LLMUsageMetrics(run_id="run_123", tokens_prompt=100, tokens_completion=50, total_tokens=150),
                success=True
            )
        for _ in range(3):
            collector.add_llm_usage(
                LLMUsageMetrics(run_id="run_123", tokens_prompt=80, tokens_completion=0, total_tokens=80),
                success=False
            )
        collector.add_llm_usage(
            LLMUsageMetrics(run_id="run_123", tokens_prompt=200, tokens_completion=100, total_tokens=300),
            success=True
        )
        
        assert collector.total_tokens == 600
        assert collector.failed_llm_calls_tokens == 240
        
        summary = collector.get_summary("run_123")
        assert summary.tokens_successful == 600
        assert summary.tokens_billable_estimate == 840 
