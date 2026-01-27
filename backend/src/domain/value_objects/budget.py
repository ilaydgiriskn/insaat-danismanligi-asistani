"""Budget value object representing user's financial capacity."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Budget:
    """
    Immutable value object representing a user's budget for property purchase.
    
    Attributes:
        min_amount: Minimum budget amount
        max_amount: Maximum budget amount
        currency: Currency code (default: TRY for Turkish Lira)
    """

    min_amount: int
    max_amount: int
    currency: str = "TRY"

    def __post_init__(self) -> None:
        """Validate budget constraints."""
        if self.min_amount < 0:
            raise ValueError("Minimum budget cannot be negative")
        if self.max_amount < 0:
            raise ValueError("Maximum budget cannot be negative")
        if self.min_amount > self.max_amount:
            raise ValueError("Minimum budget cannot exceed maximum budget")

    def __str__(self) -> str:
        return f"{self.min_amount:,} - {self.max_amount:,} {self.currency}"
