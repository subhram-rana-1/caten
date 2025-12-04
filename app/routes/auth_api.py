"""Authentication API routes."""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import structlog

from app.config import settings
from app.models import LoginRequest, LoginResponse, AuthVendor, UserInfo
from app.database.connection import get_db
from app.services.auth_service import validate_google_authentication
from app.services.jwt_service import generate_access_token, get_token_expiry
from app.services.database_service import get_or_create_user_by_google_sub, get_or_create_user_session
from app.exceptions import CatenException

logger = structlog.get_logger()

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="User login with OAuth",
    description="Authenticate user using OAuth provider (Google) and return access token"
)
async def login(
    request: LoginRequest,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Login endpoint that validates OAuth token and returns JWT access token.
    
    - Validates the auth vendor
    - For GOOGLE: validates Google ID token
    - Creates/updates user records in database
    - Generates JWT access token
    - Sets refresh token in httpOnly secure cookie
    """
    try:
        # Check auth vendor
        if request.authVendor == AuthVendor.GOOGLE:
            # Validate Google authentication
            google_data = validate_google_authentication(request.idToken)
            
            # Validate aud field
            if google_data.get('aud') != settings.google_oauth_client_id:
                logger.warning(
                    "Token audience mismatch",
                    expected=settings.google_oauth_client_id,
                    received=google_data.get('aud')
                )
                raise HTTPException(
                    status_code=401,
                    detail="Invalid token audience"
                )
            
            # Get or create user by sub
            sub = google_data.get('sub')
            if not sub:
                raise HTTPException(
                    status_code=401,
                    detail="Missing sub field in token"
                )
            
            user_id, google_auth_info_id, is_new_user = get_or_create_user_by_google_sub(
                db, sub, google_data
            )
            
            # Get or create/update user session
            session_id, refresh_token, refresh_token_expires_at = get_or_create_user_session(
                db, 'GOOGLE', google_auth_info_id, is_new_user
            )
            
            # Prepare user data for JWT
            given_name = google_data.get('given_name', '')
            family_name = google_data.get('family_name', '')
            name = f"{given_name} {family_name}".strip() or google_data.get('name', '')
            
            # Generate JWT access token
            issued_at = datetime.utcnow()
            expire_at = get_token_expiry(issued_at)
            
            access_token = generate_access_token(
                sub=sub,
                email=google_data.get('email', ''),
                name=name,
                first_name=given_name,
                last_name=family_name,
                email_verified=google_data.get('email_verified', False),
                issued_at=issued_at,
                expire_at=expire_at
            )
            
            # Set refresh token in httpOnly secure cookie
            response.set_cookie(
                key="refreshToken",
                value=refresh_token,
                httponly=True,
                secure=True,
                samesite="lax",
                expires=refresh_token_expires_at
            )
            
            logger.info(
                "Login successful",
                user_id=user_id,
                sub=sub,
                email=google_data.get('email')
            )
            
            # Construct user info
            user_info = UserInfo(
                id=user_id,
                name=name,
                email=google_data.get('email', ''),
                picture=google_data.get('picture')
            )
            
            # Return new response structure
            return LoginResponse(
                isLoggedIn=True,
                accessToken=access_token,
                accessTokenExpiresAt=int(expire_at.timestamp()),
                user=user_info
            )
        
        else:
            # Unsupported auth vendor
            logger.warning("Unsupported auth vendor", vendor=request.authVendor)
            raise HTTPException(
                status_code=404,
                detail=f"Authentication vendor '{request.authVendor}' is not supported"
            )
    
    except HTTPException:
        raise
    except CatenException as e:
        logger.error(
            "Authentication error",
            error_code=e.error_code,
            error_message=e.error_message
        )
        raise HTTPException(
            status_code=e.status_code,
            detail=e.error_message
        )
    except Exception as e:
        logger.error("Unexpected error during login", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Internal server error during authentication"
        )

