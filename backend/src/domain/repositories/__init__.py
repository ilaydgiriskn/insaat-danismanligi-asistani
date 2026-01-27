"""Domain Repository Interfaces - Abstract definitions."""

from .user_repository import IUserRepository
from .conversation_repository import IConversationRepository

__all__ = ["IUserRepository", "IConversationRepository"]
