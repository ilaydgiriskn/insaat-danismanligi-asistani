"""Pytest configuration and shared fixtures."""

import pytest
from domain.value_objects import Budget, Location
from domain.entities import UserProfile


@pytest.fixture
def valid_budget():
    """Fixture for a valid budget instance."""
    return Budget(min_amount=1000000, max_amount=5000000, currency="TRY")


@pytest.fixture
def complete_user_profile():
    """Fixture for a complete user profile with all mandatory fields."""
    profile = UserProfile()
    profile.name = "Ali"
    profile.surname = "Yılmaz"
    profile.profession = "Mühendis"
    profile.estimated_salary = "50000"
    profile.email = "ali@example.com"
    profile.current_city = "İstanbul"
    profile.location = Location(city="İzmir")  # Target location is now mandatory
    return profile


@pytest.fixture
def incomplete_user_profile():
    """Fixture for an incomplete user profile missing some mandatory fields."""
    profile = UserProfile()
    profile.name = "Ayşe"
    profile.profession = "Öğretmen"
    # Missing: surname, estimated_salary, email, current_city
    return profile
