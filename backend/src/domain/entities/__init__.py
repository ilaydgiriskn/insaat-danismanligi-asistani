"""Domain Entities - Objects with identity."""

from .user_profile import UserProfile
from .conversation import Conversation, Message, MessageRole

__all__ = ["UserProfile", "Conversation", "Message", "MessageRole"]
