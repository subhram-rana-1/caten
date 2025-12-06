"""Authentication middleware for API endpoints."""

from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, Depends, Response
from sqlalchemy.orm import Session
import structlog
from datetime import datetime, timezone

from app.config import settings
from app.database.connection import get_db
from app.services.jwt_service import decode_access_token
from app.services.database_service import (
    get_user_session_by_id,
    get_unauthenticated_user_usage,
    create_unauthenticated_user_usage,
    increment_api_usage,
    check_api_usage_limit
)

logger = structlog.get_logger()

# API endpoint to counter field name mapping
API_ENDPOINT_TO_COUNTER_FIELD = {
    # v1 APIs
    "/api/v1/image-to-text": "image_to_text_api_count_so_far",
    "/api/v1/pdf-to-text": "pdf_to_text_api_count_so_far",
    "/api/v1/important-words-from-text": "important_words_from_text_v1_api_count_so_far",
    "/api/v1/words-explanation": "words_explanation_v1_api_count_so_far",
    "/api/v1/get-more-explanations": "get_more_explanations_api_count_so_far",
    "/api/v1/get-random-paragraph": "get_random_paragraph_api_count_so_far",
    
    # v2 APIs
    "/api/v2/words-explanation": "words_explanation_api_count_so_far",
    "/api/v2/simplify": "simplify_api_count_so_far",
    "/api/v2/important-words-from-text": "important_words_from_text_v2_api_count_so_far",
    "/api/v2/ask": "ask_api_count_so_far",
    "/api/v2/pronunciation": "pronunciation_api_count_so_far",
    "/api/v2/voice-to-text": "voice_to_text_api_count_so_far",
    "/api/v2/translate": "translate_api_count_so_far",
    "/api/v2/summarise": "summarise_api_count_so_far",
    "/api/v2/web-search": "web_search_api_count_so_far",
    "/api/v2/web-search-stream": "web_search_stream_api_count_so_far",
}

# API endpoint to max limit config mapping
API_ENDPOINT_TO_MAX_LIMIT_CONFIG = {
    # v1 APIs
    "/api/v1/image-to-text": "image_to_text_api_max_limit",
    "/api/v1/pdf-to-text": "pdf_to_text_api_max_limit",
    "/api/v1/important-words-from-text": "important_words_from_text_v1_api_max_limit",
    "/api/v1/words-explanation": "words_explanation_v1_api_max_limit",
    "/api/v1/get-more-explanations": "get_more_explanations_api_max_limit",
    "/api/v1/get-random-paragraph": "get_random_paragraph_api_max_limit",
    
    # v2 APIs
    "/api/v2/words-explanation": "words_explanation_api_max_limit",
    "/api/v2/simplify": "simplify_api_max_limit",
    "/api/v2/important-words-from-text": "important_words_from_text_v2_api_max_limit",
    "/api/v2/ask": "ask_api_max_limit",
    "/api/v2/pronunciation": "pronunciation_api_max_limit",
    "/api/v2/voice-to-text": "voice_to_text_api_max_limit",
    "/api/v2/translate": "translate_api_max_limit",
    "/api/v2/summarise": "summarise_api_max_limit",
    "/api/v2/web-search": "web_search_api_max_limit",
    "/api/v2/web-search-stream": "web_search_stream_api_max_limit",
}


def get_api_counter_field_and_limit(request: Request) -> tuple[Optional[str], Optional[int]]:
    """
    Get the API counter field name and max limit for the current request.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Tuple of (counter_field_name, max_limit) or (None, None) if not found
    """
    path = request.url.path
    
    # Try exact match first
    counter_field = API_ENDPOINT_TO_COUNTER_FIELD.get(path)
    limit_config = API_ENDPOINT_TO_MAX_LIMIT_CONFIG.get(path)
    
    if counter_field and limit_config:
        max_limit = getattr(settings, limit_config, None)
        return counter_field, max_limit
    
    # If not found, return None
    return None, None


async def authenticate(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Authentication middleware that handles three cases:
    1. Authenticated user (X-Access-Token header)
    2. Unauthenticated user with ID (X-Unauthenticated-User-Id header)
    3. New unauthenticated user (no headers)
    
    IMPORTANT - INTERNAL IMPLEMENTATION DETAIL:
    ============================================
    When this function raises an HTTPException with status 401 or 429, FastAPI's
    dependency injection system will:
    1. Catch the HTTPException
    2. Use the exception handler to convert it to a JSONResponse
    3. SKIP executing the endpoint function entirely
    4. Return the error response directly to the client
    
    This means:
    - The endpoint's business logic will NOT run
    - No database queries for the endpoint will execute
    - No API service calls will be made
    - The client receives the 401/429 error immediately
    
    This is FastAPI's standard behavior: when a dependency raises an HTTPException,
    it bypasses the endpoint and uses the exception handler to return the response.
    
    Args:
        request: FastAPI request object
        response: FastAPI response object
        db: Database session
        
    Returns:
        Dictionary with authentication context
        
    Raises:
        HTTPException: 401 or 429 for authentication/authorization failures
    """
    access_token = request.headers.get("X-Access-Token")
    unauthenticated_user_id = request.headers.get("X-Unauthenticated-User-Id")
    
    # Get API counter field and max limit for this endpoint
    api_counter_field, max_limit = get_api_counter_field_and_limit(request)
    
    # Case 1: Access token header is available (authenticated user)
    if access_token:
        try:
            # Decode JWT access token
            token_payload = decode_access_token(access_token, verify_exp=False)
            user_session_pk = token_payload.get("user_session_pk")
            
            if not user_session_pk:
                logger.warning("Missing user_session_pk in access token")
                raise HTTPException(
                    status_code=401,
                    detail={
                        "errorCode": "LOGIN_REQUIRED",
                        "message": "Please login"
                    }
                )
            
            # Fetch session from database
            session_data = get_user_session_by_id(db, user_session_pk)
            
            if not session_data:
                logger.warning("User session not found", user_session_pk=user_session_pk)
                raise HTTPException(
                    status_code=401,
                    detail={
                        "errorCode": "LOGIN_REQUIRED",
                        "message": "Please login"
                    }
                )
            
            # Check if session is INVALID
            if session_data.get("access_token_state") != "VALID":
                logger.warning("User session is INVALID - returning 401, endpoint will not execute", user_session_pk=user_session_pk)
                raise HTTPException(
                    status_code=401,
                    detail={
                        "errorCode": "LOGIN_REQUIRED",
                        "reason": "Please login"
                    }
                )
            
            # Check if access_token_expires_at has expired
            access_token_expires_at = session_data.get("access_token_expires_at")
            if access_token_expires_at:
                if isinstance(access_token_expires_at, datetime):
                    expires_at = access_token_expires_at
                else:
                    # Parse if it's a string
                    expires_at = datetime.fromisoformat(str(access_token_expires_at).replace('Z', '+00:00'))
                
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                
                current_time = datetime.now(timezone.utc)
                if expires_at < current_time:
                    logger.warning(
                        "Access token expired - returning 401, endpoint will not execute",
                        user_session_pk=user_session_pk,
                        expires_at=str(expires_at),
                        current_time=str(current_time)
                    )
                    raise HTTPException(
                        status_code=401,
                        detail={
                            "errorCode": "TOKEN_EXPIRED",
                            "reason": "Please refresh the access token with refresh token"
                        }
                    )
            
            # Authenticated user - proceed with request
            logger.info("Authenticated user request", user_session_pk=user_session_pk)
            return {
                "authenticated": True,
                "user_session_pk": user_session_pk,
                "session_data": session_data
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error during authentication", error=str(e), error_type=type(e).__name__)
            raise HTTPException(
                status_code=401,
                detail="Invalid access token"
            )
    
    # Case 2: Unauthenticated user ID header is available
    elif unauthenticated_user_id:
        # CRITICAL: First check if the user_id exists in the database
        # This must happen BEFORE checking api_counter_field to prevent invalid requests
        api_usage = get_unauthenticated_user_usage(db, unauthenticated_user_id)
        
        if not api_usage:
            # Record not found - return 429 immediately
            logger.warning(
                "Unauthenticated user usage record not found - returning 429, endpoint will not execute",
                unauthenticated_user_id=unauthenticated_user_id
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "errorCode": "LOGIN_REQUIRED",
                    "message": "Please login"
                }
            )
        
        # Now check if we can determine the API counter field and max limit
        if not api_counter_field or max_limit is None:
            # If we can't determine the API, return error response (do NOT allow request)
            logger.warning(
                "Could not determine API for unauthenticated user - returning 429, endpoint will not execute",
                path=request.url.path,
                unauthenticated_user_id=unauthenticated_user_id
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "errorCode": "LOGIN_REQUIRED",
                    "message": "Please login"
                }
            )
        
        # Check if limit exceeded
        current_count = api_usage.get(api_counter_field, 0)
        if current_count >= max_limit:
            logger.warning(
                "API usage limit exceeded - returning 429, endpoint will not execute",
                unauthenticated_user_id=unauthenticated_user_id,
                api_counter_field=api_counter_field,
                current_count=current_count,
                max_limit=max_limit
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "errorCode": "LOGIN_REQUIRED",
                    "message": "Please login"
                }
            )
        
        # Increment usage counter
        increment_api_usage(db, unauthenticated_user_id, api_counter_field)
        
        logger.info(
            "Unauthenticated user request processed",
            unauthenticated_user_id=unauthenticated_user_id,
            api_counter_field=api_counter_field,
            count_after_increment=current_count + 1
        )
        
        return {
            "authenticated": False,
            "unauthenticated_user_id": unauthenticated_user_id
        }
    
    # Case 3: Neither header present (new unauthenticated user)
    else:
        if not api_counter_field or max_limit is None:
            # If we can't determine the API or max limit, return error response (do NOT allow request without tracking)
            logger.warning(
                "Could not determine API or max limit for new unauthenticated user - returning 429, endpoint will not execute",
                path=request.url.path,
                api_counter_field=api_counter_field,
                max_limit=max_limit
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "errorCode": "LOGIN_REQUIRED",
                    "message": "Please login"
                }
            )
        
        # Create new unauthenticated user record
        new_user_id = create_unauthenticated_user_usage(db, api_counter_field)
        
        logger.info(
            "New unauthenticated user created",
            unauthenticated_user_id=new_user_id,
            api_counter_field=api_counter_field
        )
        
        return {
            "authenticated": False,
            "unauthenticated_user_id": new_user_id,
            "is_new_unauthenticated_user": True
        }

