"""Unit tests for Location value object."""

import pytest
from domain.value_objects import Location


class TestLocationValidation:
    """Test Location validation logic."""

    def test_valid_location_with_district(self):
        """Test creating a valid location with district."""
        location = Location(city="İstanbul", district="Kadıköy", country="Turkey")
        assert location.city == "İstanbul"
        assert location.district == "Kadıköy"
        assert location.country == "Turkey"

    def test_valid_location_without_district(self):
        """Test creating a valid location without district."""
        location = Location(city="Ankara")
        assert location.city == "Ankara"
        assert location.district is None
        assert location.country == "Turkey"  # Default

    def test_empty_city_raises_error(self):
        """Test that empty city raises ValueError."""
        with pytest.raises(ValueError, match="City cannot be empty"):
            Location(city="")

    def test_whitespace_only_city_raises_error(self):
        """Test that whitespace-only city raises ValueError."""
        with pytest.raises(ValueError, match="City cannot be empty"):
            Location(city="   ")

    def test_none_city_raises_error(self):
        """Test that None city raises ValueError (caught by validation)."""
        with pytest.raises(ValueError, match="City cannot be empty"):
            Location(city=None)


class TestLocationFormatting:
    """Test Location string formatting."""

    def test_str_with_district(self):
        """Test __str__ includes district when present."""
        location = Location(city="İstanbul", district="Kadıköy")
        result = str(location)
        assert "Kadıköy" in result
        assert "İstanbul" in result
        assert "Turkey" in result

    def test_str_without_district(self):
        """Test __str__ excludes district when not present."""
        location = Location(city="Ankara")
        result = str(location)
        assert "Ankara" in result
        assert "Turkey" in result
        # Should not have extra comma
        assert result.count(",") == 1

    def test_immutability(self):
        """Test that Location is immutable (frozen dataclass)."""
        location = Location(city="İzmir")
        with pytest.raises(Exception):  # FrozenInstanceError
            location.city = "Ankara"
