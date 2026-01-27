"""Conversation and Message SQLAlchemy models."""

from datetime import datetime
from uuid import uuid4
from sqlalchemy import String, DateTime, Text, Boolean, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from infrastructure.database.session import Base


class ConversationModel(Base):
    """SQLAlchemy model for conversations."""
    
    __tablename__ = "conversations"
    
    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    
    # Foreign key to user profile
    user_profile_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )
    
    # Relationship to messages
    messages: Mapped[list["MessageModel"]] = relationship(
        "MessageModel",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="MessageModel.timestamp"
    )
    
    def __repr__(self) -> str:
        return f"<ConversationModel(id={self.id}, user_profile_id={self.user_profile_id})>"


class MessageModel(Base):
    """SQLAlchemy model for messages within conversations."""
    
    __tablename__ = "messages"
    
    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    
    # Foreign key to conversation
    conversation_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Message data
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )
    message_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    
    # Relationship to conversation
    conversation: Mapped["ConversationModel"] = relationship(
        "ConversationModel",
        back_populates="messages"
    )
    
    def __repr__(self) -> str:
        return f"<MessageModel(id={self.id}, role={self.role})>"
