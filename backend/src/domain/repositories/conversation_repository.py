"""Conversation repository interface - Abstract definition."""

from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from domain.entities import Conversation, Message


class IConversationRepository(ABC):
    """
    Abstract repository interface for Conversation entity.
    
    This interface defines the contract for conversation persistence.
    Concrete implementations will be in the infrastructure layer.
    """
    
    @abstractmethod
    async def create(self, conversation: Conversation) -> Conversation:
        """
        Create a new conversation.
        
        Args:
            conversation: Conversation entity to create
            
        Returns:
            Created Conversation
        """
        pass
    
    @abstractmethod
    async def get_by_id(self, conversation_id: UUID) -> Optional[Conversation]:
        """
        Retrieve a conversation by ID.
        
        Args:
            conversation_id: Conversation UUID
            
        Returns:
            Conversation if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def get_by_user_profile_id(
        self, 
        user_profile_id: UUID
    ) -> Optional[Conversation]:
        """
        Retrieve the active conversation for a user profile.
        
        Args:
            user_profile_id: User profile UUID
            
        Returns:
            Active Conversation if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def update(self, conversation: Conversation) -> Conversation:
        """
        Update an existing conversation.
        
        Args:
            conversation: Conversation entity with updated data
            
        Returns:
            Updated Conversation
        """
        pass
    
    @abstractmethod
    async def add_message(
        self, 
        conversation_id: UUID, 
        message: Message
    ) -> Conversation:
        """
        Add a message to a conversation.
        
        Args:
            conversation_id: Conversation UUID
            message: Message to add
            
        Returns:
            Updated Conversation
        """
        pass
    
    @abstractmethod
    async def delete(self, conversation_id: UUID) -> bool:
        """
        Delete a conversation.
        
        Args:
            conversation_id: Conversation UUID
            
        Returns:
            True if deleted, False if not found
        """
        pass
