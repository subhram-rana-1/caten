"""Authentication service for OAuth providers."""

from typing import Dict, Any
from google.auth.transport import requests
from google.oauth2 import id_token
import structlog

from app.config import settings
from app.exceptions import CatenException

logger = structlog.get_logger()


def validate_google_authentication(id_token_str: str) -> Dict[str, Any]:
    """
    Validate Google ID token and return decoded payload.
    
    Args:
        id_token_str: Google ID token string
        
    Returns:
        Decoded token payload with user information
        
    Raises:
        CatenException: If token validation fails or aud doesn't match
    """
    try:
        # Verify the token
        request = requests.Request()
        idinfo = id_token.verify_oauth2_token(
            id_token_str,
            request,
            settings.google_oauth_client_id
        )
        
        # Verify the audience
        if idinfo.get('aud') != settings.google_oauth_client_id:
            logger.warning(
                "Token audience mismatch",
                expected=settings.google_oauth_client_id,
                received=idinfo.get('aud')
            )
            raise CatenException(
                error_code="AUTH_001",
                error_message="Invalid token audience",
                status_code=401
            )
        
        logger.info("Google token validated successfully", sub=idinfo.get('sub'))
        return idinfo
        
    except ValueError as e:
        logger.error("Google token validation failed", error=str(e))
        raise CatenException(
            error_code="AUTH_002",
            error_message="Invalid Google ID token",
            status_code=401,
            details={"error": str(e)}
        )
    except Exception as e:
        logger.error("Unexpected error during Google token validation", error=str(e))
        raise CatenException(
            error_code="AUTH_003",
            error_message="Token validation error",
            status_code=401,
            details={"error": str(e)}
        )

