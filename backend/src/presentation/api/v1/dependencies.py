"""FastAPI dependency injection setup."""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database import get_session
from infrastructure.database.repositories import (
    SQLAlchemyUserRepository,
    SQLAlchemyConversationRepository,
)
from infrastructure.llm import LangChainService, SimplePromptManager
from application.agents import QuestionAgent, ValidationAgent, AnalysisAgent
from application.use_cases import ProcessUserMessageUseCase
from domain.repositories import IUserRepository, IConversationRepository
from application.interfaces import ILLMService, IPromptManager


# Database session dependency
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session dependency."""
    async for session in get_session():
        yield session


# Repository dependencies
async def get_user_repository(
    session: AsyncSession = None
) -> IUserRepository:
    """Get user repository dependency."""
    if session is None:
        async for s in get_session():
            session = s
            break
    return SQLAlchemyUserRepository(session)


async def get_conversation_repository(
    session: AsyncSession = None
) -> IConversationRepository:
    """Get conversation repository dependency."""
    if session is None:
        async for s in get_session():
            session = s
            break
    return SQLAlchemyConversationRepository(session)


# LLM service dependencies
def get_llm_service() -> ILLMService:
    """Get LLM service dependency."""
    return LangChainService()


def get_prompt_manager() -> IPromptManager:
    """Get prompt manager dependency."""
    return SimplePromptManager()


# Agent dependencies
def get_question_agent(
    llm_service: ILLMService = None,
    prompt_manager: IPromptManager = None,
) -> QuestionAgent:
    """Get question agent dependency."""
    if llm_service is None:
        llm_service = get_llm_service()
    if prompt_manager is None:
        prompt_manager = get_prompt_manager()
    return QuestionAgent(llm_service, prompt_manager)


def get_validation_agent(
    llm_service: ILLMService = None,
    prompt_manager: IPromptManager = None,
) -> ValidationAgent:
    """Get validation agent dependency."""
    if llm_service is None:
        llm_service = get_llm_service()
    if prompt_manager is None:
        prompt_manager = get_prompt_manager()
    return ValidationAgent(llm_service, prompt_manager)


def get_analysis_agent(
    llm_service: ILLMService = None,
    prompt_manager: IPromptManager = None,
) -> AnalysisAgent:
    """Get analysis agent dependency."""
    if llm_service is None:
        llm_service = get_llm_service()
    if prompt_manager is None:
        prompt_manager = get_prompt_manager()
    return AnalysisAgent(llm_service, prompt_manager)


# Use case dependency
async def get_process_message_use_case(
    session: AsyncSession = None,
) -> ProcessUserMessageUseCase:
    """Get process message use case dependency."""
    if session is None:
        async for s in get_session():
            session = s
            break
    
    user_repo = SQLAlchemyUserRepository(session)
    conversation_repo = SQLAlchemyConversationRepository(session)
    
    llm_service = get_llm_service()
    prompt_manager = get_prompt_manager()
    
    question_agent = QuestionAgent(llm_service, prompt_manager)
    validation_agent = ValidationAgent(llm_service, prompt_manager)
    analysis_agent = AnalysisAgent(llm_service, prompt_manager)
    
    return ProcessUserMessageUseCase(
        user_repository=user_repo,
        conversation_repository=conversation_repo,
        question_agent=question_agent,
        validation_agent=validation_agent,
        analysis_agent=analysis_agent,
    )
