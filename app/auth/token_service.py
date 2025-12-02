"""JWT access token and refresh token generation/verification service."""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Tuple, Optional
from jose import jwt, JWTError
import structlog

from app.config import settings

logger = structlog.get_logger()


def generate_access_token(user_id: int, email: str, device_id: str) -> str:
    """
    Generate a JWT access token.
    
    Args:
        user_id: User ID to include in token
        email: User email to include in token
        device_id: Device ID to include in token
        
    Returns:
        Encoded JWT access token string
    """
    # Calculate expiration time
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    
    # Create JWT payload
    payload: Dict[str, Any] = {
        "sub": str(user_id),  # Subject (user ID)
        "email": email,
        "device_id": device_id,
        "jti": str(uuid.uuid4()),  # JWT ID for potential blacklisting
        "exp": expire,  # Expiration time
        "iat": datetime.now(timezone.utc),  # Issued at
        "type": "access"  # Token type
    }
    
    # Encode and return JWT
    encoded_token = jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm
    )
    
    logger.debug("Access token generated", user_id=user_id, expires_at=expire.isoformat())
    
    return encoded_token


def verify_access_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode a JWT access token.
    
    Args:
        token: JWT access token string
        
    Returns:
        Decoded token payload dictionary
        
    Raises:
        JWTError: If token is invalid, expired, or malformed
    """
    try:
        # Decode and verify token
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm]
        )
        
        # Verify token type
        if payload.get("type") != "access":
            raise JWTError("Invalid token type")
        
        logger.debug("Access token verified", user_id=payload.get("sub"))
        
        return payload
        
    except jwt.ExpiredSignatureError:
        logger.warning("Access token expired")
        raise JWTError("Token expired")
    except JWTError as e:
        logger.warning("Access token verification failed", error=str(e))
        raise


def generate_refresh_token() -> Tuple[str, str]:
    """
    Generate a new refresh token and its hash.
    
    Returns:
        Tuple of (token, token_hash) where:
        - token: The opaque refresh token string (to return to client)
        - token_hash: SHA256 hash of the token (to store in DB)
    """
    # Generate a secure random token: UUID4 + random bytes
    token_uuid = str(uuid.uuid4())
    random_bytes = secrets.token_bytes(32)
    token = f"{token_uuid}:{random_bytes.hex()}"
    
    # Hash the token using SHA256
    token_hash = hash_refresh_token(token)
    
    logger.debug("Refresh token generated")
    
    return token, token_hash


def hash_refresh_token(token: str) -> str:
    """
    Hash a refresh token using SHA256.
    
    Args:
        token: Plain refresh token string
        
    Returns:
        SHA256 hash of the token (hexadecimal string)
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_refresh_token_hash(token: str, token_hash: str) -> bool:
    """
    Verify that a refresh token matches its stored hash.
    
    Args:
        token: Plain refresh token string
        token_hash: Stored hash of the token
        
    Returns:
        True if token matches hash, False otherwise
    """
    computed_hash = hash_refresh_token(token)
    return secrets.compare_digest(computed_hash, token_hash)


def get_refresh_token_expiry() -> datetime:
    """
    Get the expiration datetime for a new refresh token.
    
    Returns:
        Datetime when the refresh token will expire
    """
    return datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)




