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
    expire_at: datetime
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
        
    Returns:
        Signed JWT access token string
    """
    payload: Dict[str, Any] = {
        "sub": sub,
        "email": email,
        "name": name,
        "first_name": first_name,
        "last_name": last_name,
        "email_verified": email_verified,
        "iat": int(issued_at.timestamp()),
        "exp": int(expire_at.timestamp())
    }
    
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    
    logger.info("Access token generated", sub=sub, email=email)
    return token


def get_token_expiry(issued_at: datetime) -> datetime:
    """
    Calculate token expiry time based on configuration.
    
    Args:
        issued_at: Token issue time
        
    Returns:
        Expiration datetime
    """
    return issued_at + timedelta(hours=settings.access_token_expiry_hours)


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
    try:
        options = {}
        if not verify_exp:
            options["verify_exp"] = False
        
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options=options
        )
        logger.info("Access token decoded successfully", sub=payload.get('sub'), verify_exp=verify_exp)
        return payload
    except jwt.ExpiredSignatureError:
        if verify_exp:
            logger.warning("Access token has expired")
            raise
        else:
            # Decode without expiration check
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
                options={"verify_exp": False}
            )
            logger.info("Access token decoded (expired but allowed)", sub=payload.get('sub'))
            return payload
    except jwt.JWTError as e:
        logger.error("Invalid access token", error=str(e))
        raise

