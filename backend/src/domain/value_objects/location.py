"""Location value object representing geographical preferences."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Location:
    """
    Immutable value object representing a geographical location preference.
    
    Attributes:
        city: City name (required)
        district: District/neighborhood name (optional)
        country: Country name (default: Turkey)
    """

    city: str
    district: Optional[str] = None
    country: str = "Turkey"

    def __post_init__(self) -> None:
        """Validate location data."""
        if not self.city or not self.city.strip():
            raise ValueError("City cannot be empty")

    def __str__(self) -> str:
        if self.district:
            return f"{self.district}, {self.city}, {self.country}"
        return f"{self.city}, {self.country}"
