"""Custom exceptions and error handling for the FastAPI application."""

from typing import Any, Dict, Optional
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
import structlog

logger = structlog.get_logger()


class CatenException(Exception):
    """Base exception for Caten application."""
    
    def __init__(
        self,
        error_code: str,
        error_message: str,
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None
    ):
        self.error_code = error_code
        self.error_message = error_message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(error_message)


class ValidationError(CatenException):
    """Validation error exception."""
    
    def __init__(self, error_message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            error_code="VAL_001",
            error_message=error_message,
            status_code=422,
            details=details
        )


class FileValidationError(CatenException):
    """File validation error exception."""
    
    def __init__(self, error_message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            error_code="FILE_001",
            error_message=error_message,
            status_code=400,
            details=details
        )


class ImageProcessingError(CatenException):
    """Image processing error exception."""
    
    def __init__(self, error_message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            error_code="IMG_001",
            error_message=error_message,
            status_code=422,
            details=details
        )


class LLMServiceError(CatenException):
    """LLM service error exception."""
    
    def __init__(self, error_message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            error_code="LLM_001",
            error_message=error_message,
            status_code=503,
            details=details
        )


class RateLimitError(CatenException):
    """Rate limit exceeded error exception."""
    
    def __init__(self, error_message: str = "Rate limit exceeded", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            error_code="RATE_001",
            error_message=error_message,
            status_code=429,
            details=details
        )


async def caten_exception_handler(request: Request, exc: CatenException) -> JSONResponse:
    """Handle custom Caten exceptions."""
    logger.error(
        "Caten exception occurred",
        error_code=exc.error_code,
        error_message=exc.error_message,
        status_code=exc.status_code,
        details=exc.details,
        path=request.url.path,
        method=request.method
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "error_message": exc.error_message
        }
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle general exceptions."""
    logger.error(
        "Unhandled exception occurred",
        exception=str(exc),
        exception_type=type(exc).__name__,
        path=request.url.path,
        method=request.method
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "INTERNAL_001",
            "error_message": "Internal server error occurred"
        }
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTP exceptions."""
    logger.warning(
        "HTTP exception occurred",
        status_code=exc.status_code,
        detail=exc.detail,
        path=request.url.path,
        method=request.method
    )
    
    # Map common HTTP status codes to our error format
    error_code_map = {
        400: "HTTP_400",
        401: "HTTP_401", 
        403: "HTTP_403",
        404: "HTTP_404",
        405: "HTTP_405",
        422: "HTTP_422",
        500: "HTTP_500"
    }
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": error_code_map.get(exc.status_code, f"HTTP_{exc.status_code}"),
            "error_message": str(exc.detail)
        }
    )
