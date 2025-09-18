"""Health check routes."""

from datetime import datetime
from fastapi import APIRouter
from app.models import HealthCheckResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Health check",
    description="Check if the service is running properly"
)
async def health_check():
    """Health check endpoint."""
    return HealthCheckResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.utcnow().isoformat()
    )


@router.get(
    "/",
    summary="Root endpoint",
    description="Root endpoint that redirects to documentation"
)
async def root():
    """Root endpoint."""
    return {"message": "Caten API is running. Visit /docs for API documentation."}
