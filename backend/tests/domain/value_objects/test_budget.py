"""Unit tests for Budget value object."""

import pytest
from domain.value_objects import Budget


class TestBudgetValidation:
    """Test Budget validation logic."""

    def test_valid_budget_creation(self):
        """Test creating a valid budget."""
        budget = Budget(min_amount=1000000, max_amount=5000000, currency="TRY")
        assert budget.min_amount == 1000000
        assert budget.max_amount == 5000000
        assert budget.currency == "TRY"

    def test_negative_min_amount_raises_error(self):
        """Test that negative min_amount raises ValueError."""
        with pytest.raises(ValueError, match="Minimum budget cannot be negative"):
            Budget(min_amount=-1000, max_amount=5000000)

    def test_negative_max_amount_raises_error(self):
        """Test that negative max_amount raises ValueError."""
        with pytest.raises(ValueError, match="Maximum budget cannot be negative"):
            Budget(min_amount=1000000, max_amount=-5000)

    def test_min_greater_than_max_raises_error(self):
        """Test that min_amount > max_amount raises ValueError."""
        with pytest.raises(ValueError, match="Minimum budget cannot exceed maximum budget"):
            Budget(min_amount=5000000, max_amount=1000000)

    def test_min_equals_max_is_valid(self):
        """Test that min_amount == max_amount is valid (edge case)."""
        budget = Budget(min_amount=3000000, max_amount=3000000)
        assert budget.min_amount == budget.max_amount

    def test_zero_budget_is_valid(self):
        """Test that zero values are valid (edge case)."""
        budget = Budget(min_amount=0, max_amount=0)
        assert budget.min_amount == 0
        assert budget.max_amount == 0

    def test_zero_min_positive_max_is_valid(self):
        """Test that zero min with positive max is valid."""
        budget = Budget(min_amount=0, max_amount=5000000)
        assert budget.min_amount == 0
        assert budget.max_amount == 5000000


class TestBudgetFormatting:
    """Test Budget string formatting."""

    def test_str_formatting(self, valid_budget):
        """Test __str__ method formats budget correctly."""
        result = str(valid_budget)
        assert "1,000,000" in result
        assert "5,000,000" in result
        assert "TRY" in result

    def test_str_formatting_with_custom_currency(self):
        """Test __str__ with different currency."""
        budget = Budget(min_amount=10000, max_amount=50000, currency="USD")
        result = str(budget)
        assert "10,000" in result
        assert "50,000" in result
        assert "USD" in result

    def test_immutability(self, valid_budget):
        """Test that Budget is immutable (frozen dataclass)."""
        with pytest.raises(Exception):  # FrozenInstanceError
            valid_budget.min_amount = 2000000
