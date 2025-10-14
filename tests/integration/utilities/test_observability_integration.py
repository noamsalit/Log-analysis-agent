from utilities.correlation_id_management import (
    generate_correlation_id,
    set_correlation_id,
    get_correlation_id,
    clear_correlation_id
)
from utilities.callbacks.tokens_counter import TokensCounter
from utilities.callbacks.metrics_models import LLMUsageMetrics


class TestMetricsFlow:
    """Integration tests for observability components working together."""
    def test_correlation_id_in_metrics(self):
        """Test correlation ID flows through to metrics models."""
        run_id = generate_correlation_id()
        set_correlation_id(run_id)
        usage = LLMUsageMetrics(
            run_id=get_correlation_id(),
            tokens_prompt=100,
            tokens_completion=50,
            total_tokens=150
        )
        assert usage.run_id == run_id
        clear_correlation_id()
    
    def test_token_collector_aggregates_multiple_calls(self):
        """Test end-to-end token collection with successful and failed calls."""
        collector = TokensCounter()
        run_id = "run_test123"
        for i in range(3):
            usage = LLMUsageMetrics(
                run_id=run_id,
                tokens_prompt=100,
                tokens_completion=50,
                total_tokens=150
            )
            collector.add_llm_usage(usage, success=True)
        failed_usage = LLMUsageMetrics(
            run_id=run_id,
            tokens_prompt=75,
            tokens_completion=0,
            total_tokens=75
        )
        collector.add_llm_usage(failed_usage, success=False)
        summary = collector.get_summary(run_id)
        assert summary.tokens_successful == 450
        assert summary.tokens_billable_estimate == 525
