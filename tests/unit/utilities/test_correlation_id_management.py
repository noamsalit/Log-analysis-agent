from utilities.correlation_id_management import (
    generate_correlation_id,
    set_correlation_id,
    get_correlation_id,
    clear_correlation_id
)


class TestCorrelationId:
    """Test correlation ID management for tracking agent runs."""
    
    def test_generate_correlation_id_unique(self):
        """Test that generated correlation IDs are unique and properly formatted."""
        id1 = generate_correlation_id()
        id2 = generate_correlation_id()
        assert id1 != id2
        assert id1.startswith("run_")
        assert id2.startswith("run_")
        assert len(id1) == 36
    
    def test_set_and_get_correlation_id(self):
        """Test setting and retrieving a correlation ID."""
        test_id = "run_test123456"
        set_correlation_id(test_id)
        assert get_correlation_id() == test_id
    
    def test_clear_correlation_id(self):
        """Test clearing the correlation ID."""
        set_correlation_id("run_test123456")
        clear_correlation_id()
        assert get_correlation_id() is None
    
    def test_correlation_id_default(self):
        """Test default correlation ID is None."""
        clear_correlation_id()
        assert get_correlation_id() is None
