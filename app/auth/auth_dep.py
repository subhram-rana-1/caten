"""Authentication dependencies and middleware for FastAPI."""

from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timezone
from fastapi import Request, HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update, and_
import structlog

from app.database import get_db
from app.auth.models import users, refresh_tokens, unauth_device_requests
from app.auth.token_service import verify_access_token
from app.config import settings
from app.auth.schemas import ErrorResponse

logger = structlog.get_logger()
security = HTTPBearer(auto_error=False)


async def get_current_user_or_device(
    request: Request,
    authorization: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_device_id: Optional[str] = Header(None, alias="X-DEVICE-ID"),
    db: AsyncSession = Depends(get_db)
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Dependency that handles both authenticated and unauthenticated requests.
    
    Returns:
        Tuple of (user_dict, device_id):
        - If authenticated: (user_dict, None)
        - If unauthenticated: (None, device_id) after checking/incrementing device count
        
    Raises:
        HTTPException: If token invalid/expired or device limit exceeded
    """
    # Check if Authorization header is present
    if authorization and authorization.credentials:
        try:
            # Verify access token
            token_payload = verify_access_token(authorization.credentials)
            user_id = int(token_payload["sub"])
            email = token_payload.get("email")
            device_id = token_payload.get("device_id")
            
            # Fetch user from database
            result = await db.execute(
                select(users).where(
                    and_(
                        users.c.id == user_id,
                        users.c.is_active == True
                    )
                )
            )
            user_row = result.fetchone()
            
            if not user_row:
                logger.warning("User not found or inactive", user_id=user_id)
                raise HTTPException(
                    status_code=401,
                    detail={
                        "error_code": "INVALID_ACCESS_TOKEN",
                        "error_reason": "User not found or inactive"
                    }
                )
            
            # Convert row to dict
            user_dict = {
                "id": user_row.id,
                "email": user_row.email,
                "name": user_row.name,
                "picture_url": user_row.picture_url,
                "created_at": user_row.created_at,
                "last_login_at": user_row.last_login_at,
                "is_active": user_row.is_active
            }
            
            logger.debug("User authenticated", user_id=user_id, email=email)
            return user_dict, None
            
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            
            error_code = "INVALID_ACCESS_TOKEN"
            error_reason = "Access token invalid or malformed"
            
            # Check if it's an expiration error
            if "expired" in str(e).lower():
                error_code = "ACCESS_TOKEN_EXPIRED"
                error_reason = "Access token expired; please refresh"
            
            logger.warning("Token verification failed", error=str(e))
            raise HTTPException(
                status_code=401,
                detail={
                    "error_code": error_code,
                    "error_reason": error_reason
                }
            )
    
    # No authorization header - handle unauthenticated device counting
    if not x_device_id:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "BAD_REQUEST",
                "error_reason": "X-DEVICE-ID header is required"
            }
        )
    
    # Atomically increment device request count
    try:
        # Use MariaDB INSERT ... ON DUPLICATE KEY UPDATE for atomic increment
        # SQLAlchemy's on_conflict_do_update will generate the correct SQL for MariaDB
        stmt = insert(unauth_device_requests).values(
            device_id=x_device_id,
            request_count=1,
            first_seen=datetime.now(timezone.utc),
            last_request_at=datetime.now(timezone.utc)
        ).on_conflict_do_update(
            index_elements=["device_id"],
            set_={
                "request_count": unauth_device_requests.c.request_count + 1,
                "last_request_at": datetime.now(timezone.utc)
            }
        )
        
        await db.execute(stmt)
        await db.commit()
        
        # Fetch current count
        result = await db.execute(
            select(unauth_device_requests).where(
                unauth_device_requests.c.device_id == x_device_id
            )
        )
        device_row = result.fetchone()
        
        if device_row and device_row.request_count >= settings.unauthenticated_device_max_request_count:
            logger.warning(
                "Device request limit exceeded",
                device_id=x_device_id,
                count=device_row.request_count,
                limit=settings.unauthenticated_device_max_request_count
            )
            raise HTTPException(
                status_code=401,
                detail={
                    "error_code": "TOKEN_NOT_PROVIDED_LIMIT_EXCEEDED",
                    "error_reason": "Request token missing and unauthenticated device exceeded allowed anonymous requests"
                }
            )
        
        logger.debug("Unauthenticated request allowed", device_id=x_device_id, count=device_row.request_count if device_row else 0)
        return None, x_device_id
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error handling device request count", error=str(e), device_id=x_device_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "INTERNAL_ERROR",
                "error_reason": "Internal server error"
            }
        )


async def get_current_user(
    request: Request,
    authorization: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Dependency that requires a valid access token.
    
    Use this for protected endpoints that require authentication.
    
    Returns:
        User dictionary with user information
        
    Raises:
        HTTPException: If token is missing, invalid, or expired
    """
    if not authorization or not authorization.credentials:
        raise HTTPException(
            status_code=401,
            detail={
                "error_code": "INVALID_ACCESS_TOKEN",
                "error_reason": "Authorization header missing or invalid"
            }
        )
    
    try:
        # Verify access token
        token_payload = verify_access_token(authorization.credentials)
        user_id = int(token_payload["sub"])
        
        # Fetch user from database
        result = await db.execute(
            select(users).where(
                and_(
                    users.c.id == user_id,
                    users.c.is_active == True
                )
            )
        )
        user_row = result.fetchone()
        
        if not user_row:
            logger.warning("User not found or inactive", user_id=user_id)
            raise HTTPException(
                status_code=401,
                detail={
                    "error_code": "INVALID_ACCESS_TOKEN",
                    "error_reason": "User not found or inactive"
                }
            )
        
        # Convert row to dict
        user_dict = {
            "id": user_row.id,
            "email": user_row.email,
            "name": user_row.name,
            "picture_url": user_row.picture_url,
            "created_at": user_row.created_at,
            "last_login_at": user_row.last_login_at,
            "is_active": user_row.is_active
        }
        
        return user_dict
        
    except HTTPException:
        raise
    except Exception as e:
        error_code = "INVALID_ACCESS_TOKEN"
        error_reason = "Access token invalid or malformed"
        
        if "expired" in str(e).lower():
            error_code = "ACCESS_TOKEN_EXPIRED"
            error_reason = "Access token expired; please refresh"
        
        logger.warning("Token verification failed", error=str(e))
        raise HTTPException(
            status_code=401,
            detail={
                "error_code": error_code,
                "error_reason": error_reason
            }
        )

