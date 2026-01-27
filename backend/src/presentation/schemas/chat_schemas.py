"""Chat-related Pydantic schemas."""

from typing import Optional, Any
from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    """Request schema for sending a chat message."""
    
    session_id: str = Field(
        ...,
        description="User session identifier",
        min_length=1,
        max_length=255
    )
    message: str = Field(
        ...,
        description="User message content",
        min_length=1,
        max_length=5000
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "session_id": "user-123-session",
                    "message": "Merhaba, ev arıyorum"
                }
            ]
        }
    }


class ChatMessageResponse(BaseModel):
    """Response schema for chat message."""
    
    response: str = Field(..., description="Assistant's response message")
    type: str = Field(..., description="Response type: question, analysis, processing")
    is_complete: bool = Field(..., description="Whether profile is complete")
    category: Optional[str] = Field(None, description="Question category if type is question")
    analysis: Optional[dict[str, Any]] = Field(None, description="Analysis data if type is analysis")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "response": "Hangi şehirde ev arıyorsunuz?",
                    "type": "question",
                    "is_complete": False,
                    "category": "location"
                }
            ]
        }
    }


class HealthResponse(BaseModel):
    """Health check response schema."""
    
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "healthy",
                    "version": "1.0.0"
                }
            ]
        }
    }
