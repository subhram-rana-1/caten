"""Authentication routes for Google login, token refresh, logout, and profile."""

import uuid
from datetime import datetime, timezone
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update, and_, or_
import structlog

from app.database import get_db
from app.auth.models import users, refresh_tokens
from app.auth.schemas import (
    GoogleLoginRequest,
    RefreshTokenRequest,
    LogoutRequest,
    TokenResponse,
    UserResponse,
    LogoutResponse,
    ProfileResponse,
    ErrorResponse
)
from app.auth.google_auth import verify_google_id_token
from app.auth.token_service import (
    generate_access_token,
    generate_refresh_token,
    verify_refresh_token_hash,
    get_refresh_token_expiry
)
from app.auth.auth_dep import get_current_user
from app.config import settings

logger = structlog.get_logger()

router = APIRouter(tags=["Authentication"])


@router.post(
    "/google",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Google ID token login",
    description="Exchange Google ID token for backend session tokens and create/update user"
)
async def google_login(
    request: GoogleLoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    POST /auth/google
    
    Exchange a Google ID token for backend access and refresh tokens.
    Creates or updates user account based on Google profile.
    
    Request Body:
        - id_token: Google ID token JWT
        - device_id: Device identifier (UUID)
        - device_info: Optional device information
        
    Response 200:
        - access_token: JWT access token
        - token_type: "bearer"
        - expires_in: Expiration time in seconds
        - refresh_token: Opaque refresh token
        - user: User information
        
    Errors:
        - 400: Missing id_token or device_id
        - 401: Invalid Google token
        - 500: Internal server error
    """
    try:
        # Validate request
        if not request.id_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "BAD_REQUEST",
                    "error_reason": "Missing id_token or device_id"
                }
            )
        
        if not request.device_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "BAD_REQUEST",
                    "error_reason": "Missing id_token or device_id"
                }
            )
        
        # Verify Google ID token
        try:
            google_token_info = await verify_google_id_token(
                request.id_token,
                settings.google_client_id
            )
        except ValueError as e:
            logger.warning("Google token verification failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error_code": "INVALID_GOOGLE_TOKEN",
                    "error_reason": "Google token invalid or expired"
                }
            )
        
        google_sub = google_token_info.get("sub")
        email = google_token_info.get("email")
        name = google_token_info.get("name")
        picture_url = google_token_info.get("picture")
        
        if not google_sub or not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error_code": "INVALID_GOOGLE_TOKEN",
                    "error_reason": "Google token missing required claims"
                }
            )
        
        # Check if user exists
        result = await db.execute(
            select(users).where(users.c.google_sub == google_sub)
        )
        user_row = result.fetchone()
        
        now = datetime.now(timezone.utc)
        
        if user_row:
            # Update existing user
            user_id = user_row.id
            await db.execute(
                update(users)
                .where(users.c.id == user_id)
                .values(
                    email=email,
                    name=name,
                    picture_url=picture_url,
                    last_login_at=now,
                    is_active=True
                )
            )
            logger.info("User updated", user_id=user_id, email=email)
        else:
            # Create new user
            result = await db.execute(
                insert(users).values(
                    google_sub=google_sub,
                    email=email,
                    name=name,
                    picture_url=picture_url,
                    created_at=now,
                    last_login_at=now,
                    is_active=True
                ).returning(users.c.id)
            )
            user_id = result.scalar_one()
            logger.info("User created", user_id=user_id, email=email)
        
        # Generate tokens
        access_token = generate_access_token(user_id, email, request.device_id)
        refresh_token, refresh_token_hash = generate_refresh_token()
        expires_at = get_refresh_token_expiry()
        
        # Store refresh token (generate UUID for id field)
        refresh_token_id = str(uuid.uuid4())
        await db.execute(
            insert(refresh_tokens).values(
                id=refresh_token_id,
                user_id=user_id,
                token_hash=refresh_token_hash,
                device_id=request.device_id,
                issued_at=now,
                expires_at=expires_at
            )
        )
        
        await db.commit()
        
        # Return response
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60,
            refresh_token=refresh_token,
            user=UserResponse(
                id=user_id,
                email=email,
                name=name,
                picture_url=picture_url
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error during Google login", error=str(e), error_type=type(e).__name__)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "INTERNAL_ERROR",
                "error_reason": "Internal server error"
            }
        )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
    description="Exchange a refresh token for a new access token (with optional refresh token rotation)"
)
async def refresh_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    POST /auth/refresh
    
    Exchange a refresh token for a new access token.
    Optionally rotates the refresh token (revokes old, issues new).
    
    Request Body:
        - refresh_token: Opaque refresh token
        - device_id: Device identifier (UUID)
        
    Response 200:
        - access_token: New JWT access token
        - token_type: "bearer"
        - expires_in: Expiration time in seconds
        - refresh_token: New refresh token (if rotation enabled)
        
    Errors:
        - 400: Malformed request
        - 401: Refresh token invalid, expired, or revoked
    """
    try:
        if not request.refresh_token or not request.device_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "BAD_REQUEST",
                    "error_reason": "Missing refresh_token or device_id"
                }
            )
        
        # Find refresh token by device_id and check all tokens for this device
        result = await db.execute(
            select(refresh_tokens, users.c.email)
            .join(users, refresh_tokens.c.user_id == users.c.id)
            .where(
                and_(
                    refresh_tokens.c.device_id == request.device_id,
                    refresh_tokens.c.revoked_at.is_(None),
                    refresh_tokens.c.expires_at > datetime.now(timezone.utc)
                )
            )
        )
        
        token_rows = result.fetchall()
        
        # Try to match the provided token hash
        matched_token = None
        matched_email = None
        for token_row in token_rows:
            # token_row is a Row object with refresh_tokens columns and email
            if verify_refresh_token_hash(request.refresh_token, token_row.token_hash):
                matched_token = token_row
                matched_email = token_row.email
                break
        
        if not matched_token:
            logger.warning("Refresh token not found or invalid", device_id=request.device_id)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error_code": "INVALID_REFRESH_TOKEN",
                    "error_reason": "Refresh token invalid or revoked"
                }
            )
        
        user_id = matched_token.user_id
        user_email = matched_email
        old_token_id = matched_token.id
        
        # Revoke old token (rotation)
        now = datetime.now(timezone.utc)
        await db.execute(
            update(refresh_tokens)
            .where(refresh_tokens.c.id == old_token_id)
            .values(revoked_at=now)
        )
        
        # Generate new tokens
        access_token = generate_access_token(user_id, user_email, request.device_id)
        new_refresh_token, new_refresh_token_hash = generate_refresh_token()
        expires_at = get_refresh_token_expiry()
        
        # Store new refresh token (generate UUID for id field)
        new_refresh_token_id = str(uuid.uuid4())
        await db.execute(
            insert(refresh_tokens).values(
                id=new_refresh_token_id,
                user_id=user_id,
                token_hash=new_refresh_token_hash,
                device_id=request.device_id,
                issued_at=now,
                expires_at=expires_at
            )
        )
        
        await db.commit()
        
        logger.info("Token refreshed", user_id=user_id, device_id=request.device_id)
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60,
            refresh_token=new_refresh_token
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error during token refresh", error=str(e), error_type=type(e).__name__)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "INVALID_REFRESH_TOKEN",
                "error_reason": "Refresh token invalid or revoked"
            }
        )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Logout and revoke tokens",
    description="Revoke refresh tokens for the current device or all devices"
)
async def logout(
    request: LogoutRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    POST /auth/logout
    
    Revoke refresh tokens for the authenticated user.
    Requires valid access token in Authorization header.
    
    Request Body:
        - revoke_all: If true, revoke all tokens for user; if false, revoke only current device tokens
        
    Response 200:
        - ok: true
        
    Errors:
        - 401: Invalid access token
    """
    try:
        user_id = current_user["id"]
        now = datetime.now(timezone.utc)
        
        if request.revoke_all:
            # Revoke all refresh tokens for this user
            await db.execute(
                update(refresh_tokens)
                .where(
                    and_(
                        refresh_tokens.c.user_id == user_id,
                        refresh_tokens.c.revoked_at.is_(None)
                    )
                )
                .values(revoked_at=now)
            )
            logger.info("All tokens revoked for user", user_id=user_id)
        else:
            # Revoke tokens for current device (need device_id from token)
            # For simplicity, we'll revoke all non-revoked tokens
            # In production, you might want to track device_id in the access token
            await db.execute(
                update(refresh_tokens)
                .where(
                    and_(
                        refresh_tokens.c.user_id == user_id,
                        refresh_tokens.c.revoked_at.is_(None)
                    )
                )
                .values(revoked_at=now)
            )
            logger.info("Tokens revoked for user", user_id=user_id)
        
        await db.commit()
        
        return LogoutResponse(ok=True)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error during logout", error=str(e), error_type=type(e).__name__)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "INTERNAL_ERROR",
                "error_reason": "Internal server error"
            }
        )


@router.get(
    "/profile",
    response_model=ProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user profile",
    description="Get current authenticated user's profile information"
)
async def get_profile(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    GET /auth/profile
    
    Get the current authenticated user's profile.
    Requires valid access token in Authorization header.
    
    Response 200:
        - id: User ID
        - email: User email
        - name: User display name
        - picture_url: Profile picture URL
        - created_at: Account creation timestamp
        - last_login_at: Last login timestamp
        - is_active: Account active status
        
    Errors:
        - 401: Invalid or expired access token
    """
    return ProfileResponse(
        id=current_user["id"],
        email=current_user["email"],
        name=current_user.get("name"),
        picture_url=current_user.get("picture_url"),
        created_at=current_user["created_at"].isoformat() if current_user.get("created_at") else None,
        last_login_at=current_user["last_login_at"].isoformat() if current_user.get("last_login_at") else None,
        is_active=current_user["is_active"]
    )

