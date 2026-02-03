"""Unit tests for UserProfile entity."""

import pytest
from domain.entities import UserProfile
from domain.value_objects import Budget, Location, PropertyPreferences
from domain.enums import QuestionCategory, PropertyType


class TestUserProfileCompleteness:
    """Test UserProfile.is_complete() logic."""

    def test_complete_profile_returns_true(self, complete_user_profile):
        """Test that profile with all mandatory fields is complete."""
        assert complete_user_profile.is_complete() is True

    def test_incomplete_profile_returns_false(self, incomplete_user_profile):
        """Test that profile missing mandatory fields is incomplete."""
        assert incomplete_user_profile.is_complete() is False

    def test_missing_name_returns_false(self):
        """Test that missing name makes profile incomplete."""
        profile = UserProfile()
        profile.surname = "Yılmaz"
        profile.profession = "Mühendis"
        profile.estimated_salary = "50000"
        profile.location = Location(city="İzmir")
        assert profile.is_complete() is False

    def test_missing_surname_returns_false(self):
        """Test that missing surname makes profile incomplete."""
        profile = UserProfile()
        profile.name = "Ali"
        profile.profession = "Mühendis"
        profile.estimated_salary = "50000"
        profile.location = Location(city="İzmir")
        assert profile.is_complete() is False

    def test_missing_profession_returns_false(self):
        """Test that missing profession makes profile incomplete."""
        profile = UserProfile()
        profile.name = "Ali"
        profile.surname = "Yılmaz"
        profile.estimated_salary = "50000"
        profile.location = Location(city="İzmir")
        assert profile.is_complete() is False

    def test_missing_salary_returns_false(self):
        """Test that missing salary makes profile incomplete."""
        profile = UserProfile()
        profile.name = "Ali"
        profile.surname = "Yılmaz"
        profile.profession = "Mühendis"
        profile.location = Location(city="İzmir")
        assert profile.is_complete() is False

    def test_missing_email_returns_true(self):
        """Test that missing email DOES NOT make profile incomplete (optional)."""
        profile = UserProfile()
        profile.name = "Ali"
        profile.surname = "Yılmaz"
        profile.profession = "Mühendis"
        profile.estimated_salary = "50000"
        profile.location = Location(city="İzmir")
        # email is None
        assert profile.is_complete() is True

    def test_missing_current_city_returns_true(self):
        """Test that missing current_city DOES NOT make profile incomplete (optional)."""
        profile = UserProfile()
        profile.name = "Ali"
        profile.surname = "Yılmaz"
        profile.profession = "Mühendis"
        profile.estimated_salary = "50000"
        profile.location = Location(city="İzmir")
        # current_city is None
        assert profile.is_complete() is True

    def test_missing_target_location_returns_false(self):
        """Test that missing target location makes profile incomplete."""
        profile = UserProfile()
        profile.name = "Ali"
        profile.surname = "Yılmaz"
        profile.profession = "Mühendis"
        profile.estimated_salary = "50000"
        # location is None
        assert profile.is_complete() is False


class TestUserProfileCategoryTracking:
    """Test category answered tracking."""

    def test_has_answered_category_returns_true(self):
        """Test has_answered_category returns True for answered category."""
        profile = UserProfile()
        profile.answered_categories.add(QuestionCategory.BUDGET)
        assert profile.has_answered_category(QuestionCategory.BUDGET) is True

    def test_has_answered_category_returns_false(self):
        """Test has_answered_category returns False for unanswered category."""
        profile = UserProfile()
        assert profile.has_answered_category(QuestionCategory.BUDGET) is False

    def test_get_unanswered_categories_returns_all_when_empty(self):
        """Test get_unanswered_categories returns all categories when none answered."""
        profile = UserProfile()
        unanswered = profile.get_unanswered_categories()
        assert len(unanswered) == len(QuestionCategory)

    def test_get_unanswered_categories_excludes_answered(self):
        """Test get_unanswered_categories excludes answered categories."""
        profile = UserProfile()
        profile.answered_categories.add(QuestionCategory.BUDGET)
        profile.answered_categories.add(QuestionCategory.LOCATION)
        unanswered = profile.get_unanswered_categories()
        assert QuestionCategory.BUDGET not in unanswered
        assert QuestionCategory.LOCATION not in unanswered


class TestUserProfileUpdateMethods:
    """Test UserProfile update methods."""

    def test_update_budget_marks_category_answered(self, valid_budget):
        """Test update_budget marks BUDGET category as answered."""
        profile = UserProfile()
        profile.update_budget(valid_budget)
        assert profile.budget == valid_budget
        assert profile.has_answered_category(QuestionCategory.BUDGET)

    def test_update_location_marks_category_answered(self):
        """Test update_location marks LOCATION category as answered."""
        profile = UserProfile()
        location = Location(city="İstanbul", district="Kadıköy")
        profile.update_location(location)
        assert profile.location == location
        assert profile.has_answered_category(QuestionCategory.LOCATION)

    def test_update_contact_info_with_email_only(self):
        """Test update_contact_info with only email."""
        profile = UserProfile()
        profile.update_contact_info(email="test@example.com")
        assert profile.email == "test@example.com"
        assert profile.phone_number is None
        assert profile.has_answered_category(QuestionCategory.EMAIL)

    def test_update_contact_info_with_phone_only(self):
        """Test update_contact_info with only phone number."""
        profile = UserProfile()
        profile.update_contact_info(phone_number="5551234567")
        assert profile.phone_number == "5551234567"
        assert profile.email is None
        assert profile.has_answered_category(QuestionCategory.PHONE_NUMBER)

    def test_update_contact_info_with_both(self):
        """Test update_contact_info with both email and phone."""
        profile = UserProfile()
        profile.update_contact_info(email="test@example.com", phone_number="5551234567")
        assert profile.email == "test@example.com"
        assert profile.phone_number == "5551234567"
        assert profile.has_answered_category(QuestionCategory.EMAIL)
        assert profile.has_answered_category(QuestionCategory.PHONE_NUMBER)

    def test_update_family_size_marks_category_answered(self):
        """Test update_family_size marks FAMILY_SIZE category as answered."""
        profile = UserProfile()
        profile.update_family_size(4)
        assert profile.family_size == 4
        assert profile.has_answered_category(QuestionCategory.FAMILY_SIZE)

    def test_update_name_sets_name(self):
        """Test update_name sets the name field."""
        profile = UserProfile()
        profile.update_name("Mehmet")
        assert profile.name == "Mehmet"

    def test_update_property_preferences_marks_categories(self):
        """Test update_property_preferences marks relevant categories."""
        profile = UserProfile()
        prefs = PropertyPreferences(
            property_type=PropertyType.APARTMENT,
            min_rooms=2,
            max_rooms=4
        )
        profile.update_property_preferences(prefs)
        assert profile.property_preferences == prefs
        assert profile.has_answered_category(QuestionCategory.PROPERTY_TYPE)
        assert profile.has_answered_category(QuestionCategory.ROOMS)
