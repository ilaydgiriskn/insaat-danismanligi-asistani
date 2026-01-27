"""SQLAlchemy implementation of conversation repository."""

from typing import Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from domain.entities import Conversation, Message, MessageRole
from domain.repositories import IConversationRepository
from infrastructure.database.models import ConversationModel, MessageModel


class SQLAlchemyConversationRepository(IConversationRepository):
    """Concrete implementation of IConversationRepository using SQLAlchemy."""
    
    def __init__(self, session: AsyncSession):
        """Initialize repository with database session."""
        self.session = session
    
    async def create(self, conversation: Conversation) -> Conversation:
        """Create a new conversation in the database."""
        model = self._entity_to_model(conversation)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model, ["messages"])
        return self._model_to_entity(model)
    
    async def get_by_id(self, conversation_id: UUID) -> Optional[Conversation]:
        """Retrieve a conversation by ID."""
        stmt = (
            select(ConversationModel)
            .where(ConversationModel.id == conversation_id)
            .options(selectinload(ConversationModel.messages))
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        
        if model is None:
            return None
        
        return self._model_to_entity(model)
    
    async def get_by_user_profile_id(
        self, 
        user_profile_id: UUID
    ) -> Optional[Conversation]:
        """Retrieve the active conversation for a user profile."""
        stmt = (
            select(ConversationModel)
            .where(
                ConversationModel.user_profile_id == user_profile_id,
                ConversationModel.is_active == True
            )
            .options(selectinload(ConversationModel.messages))
            .order_by(ConversationModel.created_at.desc())
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        
        if model is None:
            return None
        
        return self._model_to_entity(model)
    
    async def update(self, conversation: Conversation) -> Conversation:
        """Update an existing conversation."""
        stmt = (
            select(ConversationModel)
            .where(ConversationModel.id == conversation.id)
            .options(selectinload(ConversationModel.messages))
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        
        if model is None:
            raise ValueError(f"Conversation {conversation.id} not found")
        
        self._update_model_from_entity(model, conversation)
        await self.session.flush()
        await self.session.refresh(model, ["messages"])
        
        return self._model_to_entity(model)
    
    async def add_message(
        self, 
        conversation_id: UUID, 
        message: Message
    ) -> Conversation:
        """Add a message to a conversation."""
        stmt = (
            select(ConversationModel)
            .where(ConversationModel.id == conversation_id)
            .options(selectinload(ConversationModel.messages))
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        
        if model is None:
            raise ValueError(f"Conversation {conversation_id} not found")
        
        message_model = MessageModel(
            id=message.id,
            conversation_id=conversation_id,
            role=message.role.value,
            content=message.content,
            timestamp=message.timestamp,
            additional_data=message.metadata,
        )
        
        model.messages.append(message_model)
        await self.session.flush()
        await self.session.refresh(model, ["messages"])
        
        return self._model_to_entity(model)
    
    async def delete(self, conversation_id: UUID) -> bool:
        """Delete a conversation."""
        stmt = select(ConversationModel).where(ConversationModel.id == conversation_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        
        if model is None:
            return False
        
        await self.session.delete(model)
        await self.session.flush()
        return True
    
    def _entity_to_model(self, entity: Conversation) -> ConversationModel:
        """Convert domain entity to ORM model."""
        model = ConversationModel(
            id=entity.id,
            user_profile_id=entity.user_profile_id,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            is_active=entity.is_active,
        )
        
        for message in entity.messages:
            message_model = MessageModel(
                id=message.id,
                conversation_id=entity.id,
                role=message.role.value,
                content=message.content,
                timestamp=message.timestamp,
                additional_data=message.metadata,
            )
            model.messages.append(message_model)
        
        return model
    
    def _update_model_from_entity(
        self, 
        model: ConversationModel, 
        entity: Conversation
    ) -> None:
        """Update ORM model from domain entity."""
        model.updated_at = entity.updated_at
        model.is_active = entity.is_active
        
        model.messages.clear()
        for message in entity.messages:
            message_model = MessageModel(
                id=message.id,
                conversation_id=entity.id,
                role=message.role.value,
                content=message.content,
                timestamp=message.timestamp,
                additional_data=message.metadata,
            )
            model.messages.append(message_model)
    
    def _model_to_entity(self, model: ConversationModel) -> Conversation:
        """Convert ORM model to domain entity."""
        messages = [
            Message(
                id=msg.id,
                role=MessageRole(msg.role),
                content=msg.content,
                timestamp=msg.timestamp,
                metadata=msg.additional_data,
            )
            for msg in sorted(model.messages, key=lambda m: m.timestamp)
        ]
        
        entity = Conversation(
            id=model.id,
            user_profile_id=model.user_profile_id,
            messages=messages,
            created_at=model.created_at,
            updated_at=model.updated_at,
            is_active=model.is_active,
        )
        
        return entity
