"""Question categories for organizing user information collection."""

from enum import Enum


class QuestionCategory(str, Enum):
    """Categories of questions asked to users during information gathering."""

    # Introduction Phase (Personal Info)
    NAME = "name"
    EMAIL = "email"
    PHONE = "phone"
    HOMETOWN = "hometown"
    PROFESSION = "profession"
    MARITAL_STATUS = "marital_status"
    CHILDREN = "children"
    SALARY = "salary"
    HOBBIES = "hobbies"
    PETS = "pets"
    
    # Property Search Phase
    BUDGET = "budget"
    LOCATION = "location"
    PROPERTY_TYPE = "property_type"
    SIZE = "size"
    ROOMS = "rooms"
    FEATURES = "features"
    TIMELINE = "timeline"
    FAMILY_SIZE = "family_size"
    LIFESTYLE = "lifestyle"
    PRIORITIES = "priorities"

    def __str__(self) -> str:
        return self.value
