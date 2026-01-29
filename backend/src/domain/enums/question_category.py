"""Question categories for organizing user information collection."""

from enum import Enum


class QuestionCategory(str, Enum):
    """Categories of questions asked to users during information gathering."""

    NAME = "name"
    SURNAME = "surname"
    HOMETOWN = "hometown"
    PROFESSION = "profession"
    MARITAL_STATUS = "marital_status"
    CHILDREN = "children"
    HOBBIES = "hobbies"
    EMAIL = "email"
    PHONE_NUMBER = "phone_number"
    ESTIMATED_SALARY = "estimated_salary"
    PRIORITIES = "priorities"
    LOCATION = "location"
    ROOMS = "rooms"
    SOCIAL_AMENITIES = "social_amenities"
    PURCHASE_PURPOSE = "purchase_purpose"

    def __str__(self) -> str:
        return self.value
