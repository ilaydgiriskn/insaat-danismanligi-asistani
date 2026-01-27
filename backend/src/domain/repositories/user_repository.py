"""User repository interface - Abstract definition."""

from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from domain.entities import UserProfile


class IUserRepository(ABC):
    """
    Abstract repository interface for UserProfile entity.
    
    This interface defines the contract for user profile persistence.
    Concrete implementations will be in the infrastructure layer.
    """
    
    @abstractmethod
    async def create(self, user_profile: UserProfile) -> UserProfile:
        """
        Create a new user profile.
        
        Args:
            user_profile: UserProfile entity to create
            
        Returns:
            Created UserProfile
        """
        pass
    
    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> Optional[UserProfile]:
        """
        Retrieve a user profile by ID.
        
        Args:
            user_id: User profile UUID
            
        Returns:
            UserProfile if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def get_by_session_id(self, session_id: str) -> Optional[UserProfile]:
        """
        Retrieve a user profile by session ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            UserProfile if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def update(self, user_profile: UserProfile) -> UserProfile:
        """
        Update an existing user profile.
        
        Args:
            user_profile: UserProfile entity with updated data
            
        Returns:
            Updated UserProfile
        """
        pass
    
    @abstractmethod
    async def delete(self, user_id: UUID) -> bool:
        """
        Delete a user profile.
        
        Args:
            user_id: User profile UUID
            
        Returns:
            True if deleted, False if not found
        """
        pass
