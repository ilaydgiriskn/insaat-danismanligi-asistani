"""User profile entity representing a user in the system."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from domain.value_objects import Budget, Location, PropertyPreferences
from domain.enums import QuestionCategory


@dataclass
class UserProfile:
    """
    Entity representing a user's profile with their property preferences.
    
    This is a mutable entity with identity (id).
    """

    id: UUID = field(default_factory=uuid4)
    session_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    # User information
    name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    hometown: Optional[str] = None
    profession: Optional[str] = None
    marital_status: Optional[str] = None
    has_children: Optional[bool] = None
    hobbies: list[str] = field(default_factory=list)
    estimated_salary: Optional[str] = None
    
    # Preferences (Value Objects)
    budget: Optional[Budget] = None
    location: Optional[Location] = None
    property_preferences: Optional[PropertyPreferences] = None
    
    # Additional information
    family_size: Optional[int] = None
    
    # Tracking
    answered_categories: set[QuestionCategory] = field(default_factory=set)
    
    def update_budget(self, budget: Budget) -> None:
        """Update user's budget preference."""
        self.budget = budget
        self.answered_categories.add(QuestionCategory.BUDGET)
        self._mark_updated()
    
    def update_location(self, location: Location) -> None:
        """Update user's location preference."""
        self.location = location
        self.answered_categories.add(QuestionCategory.LOCATION)
        self._mark_updated()
    
    def update_property_preferences(self, preferences: PropertyPreferences) -> None:
        """Update user's property preferences."""
        self.property_preferences = preferences
        self.answered_categories.add(QuestionCategory.PROPERTY_TYPE)
        if preferences.min_rooms is not None or preferences.max_rooms is not None:
            self.answered_categories.add(QuestionCategory.ROOMS)
        self._mark_updated()
    
    def update_family_size(self, family_size: int) -> None:
        """Update family size information."""
        self.family_size = family_size
        self.answered_categories.add(QuestionCategory.FAMILY_SIZE)
        self._mark_updated()
    
    def update_name(self, name: str) -> None:
        """Update user's name."""
        self.name = name
        self._mark_updated()
    
    def update_contact_info(self, email: Optional[str] = None, phone_number: Optional[str] = None) -> None:
        """Update user's contact information."""
        if email:
            self.email = email
            self.answered_categories.add(QuestionCategory.EMAIL)
        if phone_number:
            self.phone_number = phone_number
            self.answered_categories.add(QuestionCategory.PHONE_NUMBER)
        self._mark_updated()
    
    def has_answered_category(self, category: QuestionCategory) -> bool:
        """Check if a question category has been answered."""
        return category in self.answered_categories
    
    def get_unanswered_categories(self) -> set[QuestionCategory]:
        """Get all unanswered question categories."""
        all_categories = set(QuestionCategory)
        return all_categories - self.answered_categories
    
    def is_complete(self) -> bool:
        """
        Check if profile has sufficient information for full analysis.
        """
        has_basic = bool(self.name and (self.profession or self.hometown) and self.marital_status and self.hobbies)
        has_property = bool(self.budget and self.location and self.property_preferences and self.property_preferences.min_rooms)
        return has_basic and has_property
    
    def _mark_updated(self) -> None:
        """Mark the entity as updated."""
        self.updated_at = datetime.utcnow()
    
    def __str__(self) -> str:
        return f"UserProfile(id={self.id}, session_id={self.session_id})"
