"""Chat endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from presentation.schemas import ChatMessageRequest, ChatMessageResponse
from presentation.api.v1.dependencies import get_db_session, get_process_message_use_case
from application.use_cases import ProcessUserMessageUseCase
from infrastructure.config import get_logger

router = APIRouter(prefix="/chat", tags=["chat"])
logger = get_logger(__name__)


@router.post("/message", response_model=ChatMessageResponse)
async def send_message(
    request: ChatMessageRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ChatMessageResponse:
    """
    Send a message and get a response from the AI assistant.
    """
    try:
        logger.info(f"Received message from session: {request.session_id}")
        logger.info(f"Message content: {request.message[:100]}")
        
        # Get use case with session
        use_case = await get_process_message_use_case(session)
        logger.info("Use case created successfully")
        
        # Process message
        result = await use_case.execute(
            session_id=request.session_id,
            user_message=request.message,
        )
        
        logger.info(f"Result: {result}")
        
        # Ensure all required fields are present
        response_data = {
            "response": result.get("response", "Bir hata oluştu"),
            "type": result.get("type", "error"),
            "is_complete": result.get("is_complete", False),
            "category": result.get("category"),
            "analysis": result.get("analysis"),
        }
        
        return ChatMessageResponse(**response_data)
        
    except Exception as e:
        logger.error(f"CRITICAL ERROR processing message: {str(e)}", exc_info=True)
        # Return error response instead of raising HTTPException
        return ChatMessageResponse(
            response="Bir hata oluştu ama korkma, tekrar dene! 😊",
            type="error",
            is_complete=False,
            category=None,
            analysis=None,
        )
