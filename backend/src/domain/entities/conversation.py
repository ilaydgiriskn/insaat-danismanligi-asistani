"""Conversation entity representing chat history."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from enum import Enum


class MessageRole(str, Enum):
    """Role of the message sender."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class Message:
    """
    Value object representing a single message in a conversation.
    
    Attributes:
        id: Unique message identifier
        role: Who sent the message (user/assistant/system)
        content: Message content
        timestamp: When the message was created
        metadata: Optional metadata (e.g., agent name)
    """
    
    id: UUID = field(default_factory=uuid4)
    role: MessageRole = MessageRole.USER
    content: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        """Validate message."""
        if not self.content or not self.content.strip():
            raise ValueError("Message content cannot be empty")
    
    def is_from_user(self) -> bool:
        """Check if message is from user."""
        return self.role == MessageRole.USER
    
    def is_from_assistant(self) -> bool:
        """Check if message is from assistant."""
        return self.role == MessageRole.ASSISTANT
    
    def to_dict(self) -> dict:
        """Convert message to dictionary."""
        return {
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }
    
    def __str__(self) -> str:
        return f"{self.role.value}: {self.content[:50]}..."


@dataclass
class Conversation:
    """
    Entity representing a conversation between user and assistant.
    
    This is an aggregate root that manages the conversation history.
    """
    
    id: UUID = field(default_factory=uuid4)
    user_profile_id: UUID = field(default_factory=uuid4)
    messages: list[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    is_active: bool = True
    
    def add_user_message(self, content: str, metadata: Optional[dict] = None) -> Message:
        """
        Add a user message to the conversation.
        
        Args:
            content: Message content
            metadata: Optional metadata
            
        Returns:
            The created message
        """
        message = Message(
            role=MessageRole.USER,
            content=content,
            metadata=metadata or {}
        )
        self.messages.append(message)
        self._mark_updated()
        return message
    
    def add_assistant_message(
        self, 
        content: str, 
        metadata: Optional[dict] = None
    ) -> Message:
        """
        Add an assistant message to the conversation.
        
        Args:
            content: Message content
            metadata: Optional metadata (e.g., agent name)
            
        Returns:
            The created message
        """
        message = Message(
            role=MessageRole.ASSISTANT,
            content=content,
            metadata=metadata or {}
        )
        self.messages.append(message)
        self._mark_updated()
        return message
    
    def get_recent_messages(self, count: int = 10) -> list[Message]:
        """
        Get the most recent messages.
        
        Args:
            count: Number of recent messages to retrieve
            
        Returns:
            List of recent messages
        """
        return self.messages[-count:] if len(self.messages) > count else self.messages
    
    def get_message_count(self) -> int:
        """Get total number of messages."""
        return len(self.messages)
    
    def _mark_updated(self) -> None:
        """Mark the entity as updated."""
        self.updated_at = datetime.utcnow()
    
    def get_last_assistant_message(self) -> Optional[Message]:
        """Get the last message sent by assistant."""
        for msg in reversed(self.messages):
            if msg.role == MessageRole.ASSISTANT:
                return msg
        return None
        
    def __str__(self) -> str:
        return f"Conversation(id={self.id}, messages={len(self.messages)})"
