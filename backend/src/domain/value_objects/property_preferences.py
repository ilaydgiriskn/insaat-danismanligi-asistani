"""Property preferences value object."""

from dataclasses import dataclass
from typing import Optional
from domain.enums import PropertyType


@dataclass(frozen=True)
class PropertyPreferences:
    """
    Immutable value object representing user's property preferences.
    
    Attributes:
        property_type: Preferred type of property
        min_rooms: Minimum number of rooms
        max_rooms: Maximum number of rooms
        has_balcony: Whether balcony is required
        has_parking: Whether parking is required
    """

    property_type: PropertyType
    min_rooms: Optional[int] = None
    max_rooms: Optional[int] = None
    has_balcony: Optional[bool] = None
    has_parking: Optional[bool] = None

    def __str__(self) -> str:
        parts = [str(self.property_type)]
        if self.min_rooms is not None or self.max_rooms is not None:
            parts.append(f"{self.min_rooms or 0}-{self.max_rooms or '∞'} rooms")
        return ", ".join(parts)
