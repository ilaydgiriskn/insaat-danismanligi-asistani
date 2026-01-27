"""Health check endpoint."""

from fastapi import APIRouter

from presentation.schemas import HealthResponse
from infrastructure.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    
    Returns service status and version information.
    """
    settings = get_settings()
    
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
    )
