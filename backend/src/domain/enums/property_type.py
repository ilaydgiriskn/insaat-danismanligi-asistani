"""Property types for real estate classification."""

from enum import Enum


class PropertyType(str, Enum):
    """Types of properties available in the real estate market."""

    APARTMENT = "apartment"
    HOUSE = "house"
    VILLA = "villa"
    STUDIO = "studio"
    PENTHOUSE = "penthouse"
    DUPLEX = "duplex"
    LAND = "land"
    COMMERCIAL = "commercial"

    def __str__(self) -> str:
        return self.value
