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

