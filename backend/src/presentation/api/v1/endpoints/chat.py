"""Chat endpoints with robust error handling."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from presentation.schemas import ChatMessageRequest, ChatMessageResponse
from presentation.api.v1.dependencies import get_db_session, get_process_message_use_case
from infrastructure.config import get_logger

router = APIRouter(prefix="/chat", tags=["chat"])
logger = get_logger(__name__)


@router.post("/message", response_model=ChatMessageResponse)
async def send_message(
    request: ChatMessageRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ChatMessageResponse:
    """Send a message and get a response from the AI assistant."""
    try:
        logger.info(f"Received message from session: {request.session_id}")
        
        # Get use case
        use_case = await get_process_message_use_case(session)
        
        # Process message
        result = await use_case.execute(
            session_id=request.session_id,
            user_message=request.message,
        )
        
        # Ensure all required fields with safe defaults
        return ChatMessageResponse(
            response=result.get("response") or "Devam edelim!",
            type=result.get("type") or "question",
            is_complete=bool(result.get("is_complete", False)),  # Force bool
            category=result.get("category"),
            analysis=result.get("analysis"),
        )
        
    except Exception as e:
        logger.error(f"Chat error: {str(e)}", exc_info=True)
        
        # Check for quota error
        error_str = str(e).lower()
        if "quota" in error_str or "rate" in error_str:
            return ChatMessageResponse(
                response="API kotası dolmuş görünüyor. Lütfen biraz bekleyin veya API anahtarınızı kontrol edin.",
                type="error",
                is_complete=False,
                category=None,
                analysis=None,
            )
        
        return ChatMessageResponse(
            response="Bir aksaklık oldu, tekrar deneyelim!",
            type="error",
            is_complete=False,
            category=None,
            analysis=None,
        )
@router.get("/{session_id}/history")
async def get_history(
    session_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Get conversation history for resumption."""
    try:
        from application.use_cases.get_conversation_history import GetConversationHistoryUseCase
        from infrastructure.database.repositories.sqlalchemy_user_repository import SQLAlchemyUserRepository
        from infrastructure.database.repositories.sqlalchemy_conversation_repository import SQLAlchemyConversationRepository
        
        user_repo = SQLAlchemyUserRepository(session)
        conv_repo = SQLAlchemyConversationRepository(session)
        
        use_case = GetConversationHistoryUseCase(user_repo, conv_repo)
        result = await use_case.execute(session_id)
        
        if not result:
            return {"found": False}
            
        return {"found": True, "data": result}
        
    except Exception as e:
        logger.error(f"History error: {str(e)}", exc_info=True)
        return {"found": False, "error": str(e)}
