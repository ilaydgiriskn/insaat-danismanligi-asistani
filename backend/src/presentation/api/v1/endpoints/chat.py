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
    
    This endpoint:
    1. Receives user message
    2. Updates user profile
    3. Determines next action (ask question or provide analysis)
    4. Returns appropriate response
    """
    try:
        logger.info(f"Received message from session: {request.session_id}")
        
        # Get use case with session
        use_case = await get_process_message_use_case(session)
        
        # Process message
        result = await use_case.execute(
            session_id=request.session_id,
            user_message=request.message,
        )
        
        return ChatMessageResponse(**result)
        
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing your message"
        )
