"""JWT token generation service."""

from datetime import datetime, timedelta
from typing import Dict, Any
from jose import jwt
import structlog

from app.config import settings

logger = structlog.get_logger()


def generate_access_token(
    sub: str,
    email: str,
    name: str,
    first_name: str,
    last_name: str,
    email_verified: bool,
    issued_at: datetime,
    expire_at: datetime,
    user_session_pk: str
) -> str:
    """
    Generate JWT access token with user information.
    
    Args:
        sub: User subject ID (from Google)
        email: User email
        name: Full name (given_name + family_name)
        first_name: Given name
        last_name: Family name
        email_verified: Whether email is verified
        issued_at: Token issue time
        expire_at: Token expiration time
        user_session_pk: User session primary key (ID from user_session table)
        
    Returns:
        Signed JWT access token string
    """
    # Entry log with user context
    logger.info(
        "Generating JWT access token",
        function="generate_access_token",
        sub=sub,
        email=email,
        user_session_pk=user_session_pk,
        issued_at=str(issued_at),
        expire_at=str(expire_at),
        email_verified=email_verified,
        algorithm=settings.jwt_algorithm
    )
    
    payload: Dict[str, Any] = {
        "sub": sub,
        "email": email,
        "name": name,
        "first_name": first_name,
        "last_name": last_name,
        "email_verified": email_verified,
        "user_session_pk": user_session_pk,
        "iat": int(issued_at.timestamp()),
        "exp": int(expire_at.timestamp())
    }
    
    logger.debug(
        "JWT payload prepared",
        function="generate_access_token",
        sub=sub,
        payload_keys=list(payload.keys()),
        iat=payload.get("iat"),
        exp=payload.get("exp")
    )
    
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    
    token_preview = token[:8] + "..." if token and len(token) > 8 else None
    logger.info(
        "Access token generated successfully",
        function="generate_access_token",
        sub=sub,
        email=email,
        user_session_pk=user_session_pk,
        token_preview=token_preview,
        token_length=len(token) if token else 0,
        issued_at_timestamp=payload.get("iat"),
        expires_at_timestamp=payload.get("exp"),
        expires_in_seconds=payload.get("exp") - payload.get("iat")
    )
    return token


def get_token_expiry(issued_at: datetime) -> datetime:
    """
    Calculate token expiry time based on configuration.
    
    Args:
        issued_at: Token issue time
        
    Returns:
        Expiration datetime
    """
    expiry_hours = settings.access_token_expiry_hours
    expire_at = issued_at + timedelta(hours=expiry_hours)
    
    logger.debug(
        "Token expiry calculated",
        function="get_token_expiry",
        issued_at=str(issued_at),
        expiry_hours=expiry_hours,
        expire_at=str(expire_at)
    )
    
    return expire_at


def decode_access_token(token: str, verify_exp: bool = True) -> Dict[str, Any]:
    """
    Decode JWT access token and return payload.
    
    Args:
        token: JWT access token string
        verify_exp: Whether to verify token expiration (default: True)
        
    Returns:
        Decoded token payload as dictionary
        
    Raises:
        jwt.ExpiredSignatureError: If token has expired and verify_exp=True
        jwt.JWTError: If token is invalid
    """
    # Entry log with truncated token and verification settings
    token_preview = token[:8] + "..." if token and len(token) > 8 else (token if token else None)
    logger.info(
        "Decoding JWT access token",
        function="decode_access_token",
        token_preview=token_preview,
        token_length=len(token) if token else 0,
        verify_exp=verify_exp,
        algorithm=settings.jwt_algorithm
    )
    
    try:
        options = {}
        if not verify_exp:
            options["verify_exp"] = False
        
        logger.debug(
            "Starting JWT token decode",
            function="decode_access_token",
            verify_exp=verify_exp,
            options=options
        )
        
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options=options
        )
        
        logger.info(
            "Access token decoded successfully",
            function="decode_access_token",
            sub=payload.get('sub'),
            email=payload.get('email'),
            user_session_pk=payload.get('user_session_pk'),
            verify_exp=verify_exp,
            iat=payload.get('iat'),
            exp=payload.get('exp'),
            payload_keys=list(payload.keys())
        )
        return payload
    except jwt.ExpiredSignatureError as e:
        if verify_exp:
            logger.warning(
                "Access token has expired",
                function="decode_access_token",
                error=str(e),
                error_type=type(e).__name__,
                token_preview=token_preview
            )
            raise
        else:
            # Decode without expiration check
            logger.debug(
                "Access token expired but verify_exp=False, decoding anyway",
                function="decode_access_token",
                token_preview=token_preview
            )
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
                options={"verify_exp": False}
            )
            logger.info(
                "Access token decoded (expired but allowed)",
                function="decode_access_token",
                sub=payload.get('sub'),
                email=payload.get('email'),
                user_session_pk=payload.get('user_session_pk'),
                exp=payload.get('exp')
            )
            return payload
    except jwt.JWTError as e:
        logger.error(
            "Invalid access token - JWT error",
            function="decode_access_token",
            error=str(e),
            error_type=type(e).__name__,
            token_preview=token_preview,
            verify_exp=verify_exp
        )
        raise
    except Exception as e:
        logger.error(
            "Unexpected error during token decode",
            function="decode_access_token",
            error=str(e),
            error_type=type(e).__name__,
            token_preview=token_preview
        )
        raise

