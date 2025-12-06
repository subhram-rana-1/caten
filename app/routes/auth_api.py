"""Authentication API routes."""

from datetime import datetime, timezone
import traceback
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import structlog

from app.config import settings
from app.models import LoginRequest, LoginResponse, LogoutRequest, AuthVendor, UserInfo
from app.database.connection import get_db
from app.services.auth_service import validate_google_authentication
from app.services.jwt_service import generate_access_token, get_token_expiry, decode_access_token
from app.services.database_service import (
    get_or_create_user_by_google_sub, 
    get_or_create_user_session,
    invalidate_user_session,
    get_user_info_by_sub,
    get_user_session_by_id,
    update_user_session_refresh_token
)
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
        logger.info(
            "Login request received",
            auth_vendor=request.authVendor,
            has_id_token=bool(request.idToken),
            id_token_length=len(request.idToken) if request.idToken else 0
        )
        
        # Check auth vendor
        if request.authVendor == AuthVendor.GOOGLE:
            # Validate Google authentication
            logger.debug("Validating Google authentication token")
            google_data = validate_google_authentication(request.idToken)
            
            logger.info(
                "Google token validated successfully",
                sub=google_data.get('sub'),
                email=google_data.get('email'),
                email_verified=google_data.get('email_verified', False)
            )
            
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
                logger.error("Missing sub field in Google token data", google_data_keys=list(google_data.keys()))
                raise HTTPException(
                    status_code=401,
                    detail="Missing sub field in token"
                )
            
            logger.debug("Getting or creating user by Google sub", sub=sub)
            user_id, google_auth_info_id, is_new_user = get_or_create_user_by_google_sub(
                db, sub, google_data
            )
            
            logger.info(
                "User lookup/creation completed",
                user_id=user_id,
                google_auth_info_id=google_auth_info_id,
                is_new_user=is_new_user,
                sub=sub
            )
            
            # Get or create/update user session
            logger.debug(
                "Getting or creating user session",
                auth_vendor_type='GOOGLE',
                google_auth_info_id=google_auth_info_id,
                is_new_user=is_new_user
            )
            session_id, refresh_token, refresh_token_expires_at = get_or_create_user_session(
                db, 'GOOGLE', google_auth_info_id, is_new_user
            )
            
            logger.info(
                "Session created/updated",
                session_id=session_id,
                refresh_token_preview=refresh_token[:8] + "..." if refresh_token else None,
                refresh_token_expires_at=str(refresh_token_expires_at),
                expires_at_type=type(refresh_token_expires_at).__name__,
                expires_at_timezone_aware=refresh_token_expires_at.tzinfo is not None if hasattr(refresh_token_expires_at, 'tzinfo') else None
            )
            
            # Prepare user data for JWT
            given_name = google_data.get('given_name', '')
            family_name = google_data.get('family_name', '')
            name = f"{given_name} {family_name}".strip() or google_data.get('name', '')
            
            # Generate JWT access token
            issued_at = datetime.now(timezone.utc)
            expire_at = get_token_expiry(issued_at)
            
            logger.debug(
                "Generating JWT access token",
                sub=sub,
                email=google_data.get('email', ''),
                issued_at=str(issued_at),
                expire_at=str(expire_at),
                issued_at_type=type(issued_at).__name__,
                expire_at_type=type(expire_at).__name__
            )
            
            access_token = generate_access_token(
                sub=sub,
                email=google_data.get('email', ''),
                name=name,
                first_name=given_name,
                last_name=family_name,
                email_verified=google_data.get('email_verified', False),
                issued_at=issued_at,
                expire_at=expire_at,
                user_session_pk=session_id
            )
            
            logger.debug(
                "Setting refresh token cookie",
                cookie_key="refreshToken",
                refresh_token_preview=refresh_token[:8] + "..." if refresh_token else None,
                expires=str(refresh_token_expires_at),
                expires_type=type(refresh_token_expires_at).__name__,
                expires_timezone_aware=refresh_token_expires_at.tzinfo is not None if hasattr(refresh_token_expires_at, 'tzinfo') else None
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
            
            logger.debug("Cookie set successfully")
            
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
                firstName=given_name if given_name else None,
                lastName=family_name if family_name else None,
                email=google_data.get('email', ''),
                picture=google_data.get('picture')
            )
            
            # Return new response structure
            return LoginResponse(
                isLoggedIn=True,
                accessToken=access_token,
                accessTokenExpiresAt=int(expire_at.timestamp()),
                userSessionPk=session_id,
                user=user_info
            )
        
        else:
            # Unsupported auth vendor
            logger.warning("Unsupported auth vendor", vendor=request.authVendor)
            raise HTTPException(
                status_code=404,
                detail=f"Authentication vendor '{request.authVendor}' is not supported"
            )
    
    except HTTPException as e:
        logger.warning(
            "HTTP exception during login",
            status_code=e.status_code,
            detail=e.detail,
            auth_vendor=request.authVendor if hasattr(request, 'authVendor') else None
        )
        raise
    except CatenException as e:
        logger.error(
            "Authentication error",
            error_code=e.error_code,
            error_message=e.error_message,
            status_code=e.status_code,
            details=getattr(e, 'details', None),
            auth_vendor=request.authVendor if hasattr(request, 'authVendor') else None,
            traceback=traceback.format_exc()
        )
        raise HTTPException(
            status_code=e.status_code,
            detail=e.error_message
        )
    except Exception as e:
        logger.error(
            "Unexpected error during login",
            error=str(e),
            error_type=type(e).__name__,
            auth_vendor=request.authVendor if hasattr(request, 'authVendor') else None,
            traceback=traceback.format_exc()
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error during authentication"
        )


@router.post(
    "/logout",
    response_model=LoginResponse,
    summary="User logout",
    description="Logout user by invalidating their session and returning logout response"
)
async def logout(
    request: LogoutRequest,
    http_request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Logout endpoint that invalidates user session.
    
    - Extracts access token from Authorization header (Bearer token)
    - Decodes the JWT access token to get user information
    - Invalidates the user session by marking it as INVALID
    - Returns response with isLoggedIn=false and user information
    """
    try:
        # Extract access token from Authorization header
        auth_header = http_request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.warning("Missing or invalid Authorization header")
            raise HTTPException(
                status_code=401,
                detail="Missing or invalid Authorization header"
            )
        
        access_token = auth_header.replace("Bearer ", "").strip()
        if not access_token:
            logger.warning("Empty access token in Authorization header")
            raise HTTPException(
                status_code=401,
                detail="Empty access token"
            )
        
        logger.info(
            "Logout request received",
            auth_vendor=request.authVendor,
            has_access_token=bool(access_token),
            access_token_length=len(access_token)
        )
        
        # Decode the JWT access token
        # For logout, we allow expired tokens since user is logging out anyway
        try:
            logger.debug("Decoding JWT access token")
            token_payload = decode_access_token(access_token, verify_exp=False)
        except Exception as e:
            logger.warning(
                "Failed to decode access token",
                error=str(e),
                error_type=type(e).__name__
            )
            raise HTTPException(
                status_code=401,
                detail="Invalid access token"
            )
        
        # Extract sub from token
        sub = token_payload.get('sub')
        if not sub:
            logger.error("Missing sub field in token payload", token_keys=list(token_payload.keys()))
            raise HTTPException(
                status_code=401,
                detail="Missing sub field in token"
            )
        
        logger.info("Token decoded successfully", sub=sub)
        
        # Check auth vendor
        if request.authVendor == AuthVendor.GOOGLE:
            # Invalidate user session
            logger.debug(
                "Invalidating user session",
                auth_vendor_type='GOOGLE',
                sub=sub
            )
            session_invalidated = invalidate_user_session(
                db, 'GOOGLE', sub
            )
            
            if not session_invalidated:
                logger.warning(
                    "No valid session found to invalidate",
                    auth_vendor_type='GOOGLE',
                    sub=sub
                )
                # Continue anyway, as the token might already be invalidated
            
            # Get user information from database
            logger.debug("Fetching user information from database", sub=sub)
            user_data = get_user_info_by_sub(db, sub)
            
            if not user_data:
                logger.error("User not found in database", sub=sub)
                raise HTTPException(
                    status_code=404,
                    detail="User not found"
                )
            
            logger.info(
                "User information retrieved",
                user_id=user_data.get('user_id'),
                sub=sub,
                email=user_data.get('email')
            )
            
            # Get token expiry from decoded token
            exp_timestamp = token_payload.get('exp')
            access_token_expires_at = exp_timestamp if exp_timestamp else 0
            
            # Get user_session_pk from token
            user_session_pk = token_payload.get('user_session_pk', '')
            
            # Construct user info
            user_info = UserInfo(
                id=user_data.get('user_id'),
                name=user_data.get('name', ''),
                firstName=user_data.get('first_name'),
                lastName=user_data.get('last_name'),
                email=user_data.get('email', ''),
                picture=user_data.get('picture')
            )
            
            logger.info("Logout successful", user_id=user_data.get('user_id'), sub=sub)
            
            # Return response with isLoggedIn=false
            return LoginResponse(
                isLoggedIn=False,
                accessToken=access_token,  # Return the same token (though it's now invalidated)
                accessTokenExpiresAt=access_token_expires_at,
                userSessionPk=user_session_pk,
                user=user_info
            )
        
        else:
            # Unsupported auth vendor
            logger.warning("Unsupported auth vendor", vendor=request.authVendor)
            raise HTTPException(
                status_code=404,
                detail=f"Authentication vendor '{request.authVendor}' is not supported"
            )
    
    except HTTPException as e:
        logger.warning(
            "HTTP exception during logout",
            status_code=e.status_code,
            detail=e.detail,
            auth_vendor=request.authVendor if hasattr(request, 'authVendor') else None
        )
        raise
    except CatenException as e:
        logger.error(
            "Authentication error during logout",
            error_code=e.error_code,
            error_message=e.error_message,
            status_code=e.status_code,
            details=getattr(e, 'details', None),
            auth_vendor=request.authVendor if hasattr(request, 'authVendor') else None,
            traceback=traceback.format_exc()
        )
        raise HTTPException(
            status_code=e.status_code,
            detail=e.error_message
        )
    except Exception as e:
        logger.error(
            "Unexpected error during logout",
            error=str(e),
            error_type=type(e).__name__,
            auth_vendor=request.authVendor if hasattr(request, 'authVendor') else None,
            traceback=traceback.format_exc()
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error during logout"
        )


@router.post(
    "/refresh-token",
    summary="Refresh access token",
    description="Refresh the access token by validating current access token and refresh token, then issue a new refresh token"
)
async def refresh_access_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Refresh token endpoint that validates current tokens and issues a new refresh token.
    
    - Extracts access token from Authorization header (Bearer token)
    - Extracts refresh token from httpOnly secure cookie
    - Validates access token and fetches user session
    - Validates refresh token matches database and hasn't expired
    - Generates new refresh token and updates database
    - Returns new refresh token in httpOnly secure cookie
    """
    try:
        logger.info("Refresh token request received")
        
        # Extract access token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.warning("Missing or invalid Authorization header")
            raise HTTPException(
                status_code=401,
                detail={
                    "errorCode": "LOGIN_REQUIRED",
                    "reason": "Missing or invalid Authorization header"
                }
            )
        
        access_token = auth_header.replace("Bearer ", "").strip()
        if not access_token:
            logger.warning("Empty access token in Authorization header")
            raise HTTPException(
                status_code=401,
                detail={
                    "errorCode": "LOGIN_REQUIRED",
                    "reason": "Empty access token"
                }
            )
        
        # Extract refresh token from cookie
        refresh_token_from_cookie = request.cookies.get("refreshToken")
        if not refresh_token_from_cookie:
            logger.warning("Missing refresh token cookie")
            raise HTTPException(
                status_code=401,
                detail={
                    "errorCode": "LOGIN_REQUIRED",
                    "reason": "Missing refresh token"
                }
            )
        
        # Decode JWT access token to get user_session_pk
        try:
            logger.debug("Decoding JWT access token")
            token_payload = decode_access_token(access_token, verify_exp=False)
        except Exception as e:
            logger.warning(
                "Failed to decode access token",
                error=str(e),
                error_type=type(e).__name__
            )
            raise HTTPException(
                status_code=401,
                detail={
                    "errorCode": "LOGIN_REQUIRED",
                    "reason": "Invalid access token"
                }
            )
        
        # Extract user_session_pk from token
        user_session_pk = token_payload.get("user_session_pk")
        if not user_session_pk:
            logger.error("Missing user_session_pk in token payload", token_keys=list(token_payload.keys()))
            raise HTTPException(
                status_code=401,
                detail={
                    "errorCode": "LOGIN_REQUIRED",
                    "reason": "Missing user_session_pk in token"
                }
            )
        
        logger.info("Token decoded successfully", user_session_pk=user_session_pk)
        
        # Fetch user_session record by ID
        session_data = get_user_session_by_id(db, user_session_pk)
        if not session_data:
            logger.warning("User session not found", user_session_pk=user_session_pk)
            raise HTTPException(
                status_code=401,
                detail={
                    "errorCode": "LOGIN_REQUIRED",
                    "reason": "Session not found"
                }
            )
        
        # Check if access_token_state is INVALID
        if session_data.get("access_token_state") != "VALID":
            logger.warning("User session is INVALID", user_session_pk=user_session_pk)
            raise HTTPException(
                status_code=401,
                detail={
                    "errorCode": "LOGIN_REQUIRED",
                    "reason": "Session is invalid"
                }
            )
        
        # Check if refresh_token_expires_at has expired
        refresh_token_expires_at = session_data.get("refresh_token_expires_at")
        if refresh_token_expires_at:
            if isinstance(refresh_token_expires_at, datetime):
                expires_at = refresh_token_expires_at
            else:
                # Parse if it's a string
                expires_at = datetime.fromisoformat(str(refresh_token_expires_at).replace('Z', '+00:00'))
            
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            
            current_time = datetime.now(timezone.utc)
            if expires_at < current_time:
                logger.warning(
                    "Refresh token expired",
                    user_session_pk=user_session_pk,
                    expires_at=str(expires_at),
                    current_time=str(current_time)
                )
                raise HTTPException(
                    status_code=401,
                    detail={
                        "errorCode": "LOGIN_REQUIRED",
                        "reason": "Refresh token expired"
                    }
                )
        
        # Verify refresh token from cookie matches the one in database
        refresh_token_from_db = session_data.get("refresh_token")
        if refresh_token_from_cookie != refresh_token_from_db:
            logger.warning(
                "Refresh token mismatch",
                user_session_pk=user_session_pk
            )
            raise HTTPException(
                status_code=401,
                detail={
                    "errorCode": "LOGIN_REQUIRED",
                    "reason": "Invalid refresh token"
                }
            )
        
        logger.info("Refresh token validated successfully", user_session_pk=user_session_pk)
        
        # Generate new refresh token and update database
        new_refresh_token, new_refresh_token_expires_at = update_user_session_refresh_token(
            db, user_session_pk
        )
        
        logger.info(
            "New refresh token generated",
            user_session_pk=user_session_pk,
            refresh_token_preview=new_refresh_token[:8] + "..." if new_refresh_token else None,
            expires_at=str(new_refresh_token_expires_at)
        )
        
        # Set new refresh token in httpOnly secure cookie
        response.set_cookie(
            key="refreshToken",
            value=new_refresh_token,
            httponly=True,
            secure=True,
            samesite="lax",
            expires=new_refresh_token_expires_at
        )
        
        logger.info("Refresh token updated successfully", user_session_pk=user_session_pk)
        
        # Return 200 status with empty response body
        return Response(status_code=200)
    
    except HTTPException as e:
        logger.warning(
            "HTTP exception during refresh token",
            status_code=e.status_code,
            detail=e.detail
        )
        raise
    except Exception as e:
        logger.error(
            "Unexpected error during refresh token",
            error=str(e),
            error_type=type(e).__name__,
            traceback=traceback.format_exc()
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error during token refresh"
        )

