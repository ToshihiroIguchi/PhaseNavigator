from datetime import datetime
from fastapi import APIRouter

from ..core.config import settings
from ..models.responses import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        app_name=settings.app_name,
        version=settings.app_version,
        timestamp=datetime.utcnow().isoformat()
    )