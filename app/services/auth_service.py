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
    # Entry log with truncated token
    id_token_preview = id_token_str[:8] + "..." if id_token_str and len(id_token_str) > 8 else (id_token_str if id_token_str else None)
    logger.info(
        "Validating Google authentication token",
        function="validate_google_authentication",
        id_token_preview=id_token_preview,
        id_token_length=len(id_token_str) if id_token_str else 0,
        expected_client_id=settings.google_oauth_client_id
    )
    
    try:
        # Verify the token
        logger.debug(
            "Starting Google OAuth2 token verification",
            function="validate_google_authentication",
            client_id=settings.google_oauth_client_id
        )
        request = requests.Request()
        idinfo = id_token.verify_oauth2_token(
            id_token_str,
            request,
            settings.google_oauth_client_id
        )
        
        logger.debug(
            "Google OAuth2 token verification completed",
            function="validate_google_authentication",
            has_sub=bool(idinfo.get('sub')),
            has_email=bool(idinfo.get('email')),
            has_aud=bool(idinfo.get('aud'))
        )
        
        # Verify the audience
        received_aud = idinfo.get('aud')
        if received_aud != settings.google_oauth_client_id:
            logger.warning(
                "Token audience mismatch",
                function="validate_google_authentication",
                expected=settings.google_oauth_client_id,
                received=received_aud,
                sub=idinfo.get('sub')
            )
            raise CatenException(
                error_code="AUTH_001",
                error_message="Invalid token audience",
                status_code=401
            )
        
        # Success log with user information (excluding sensitive data)
        logger.info(
            "Google token validated successfully",
            function="validate_google_authentication",
            sub=idinfo.get('sub'),
            email=idinfo.get('email'),
            email_verified=idinfo.get('email_verified', False),
            has_given_name=bool(idinfo.get('given_name')),
            has_family_name=bool(idinfo.get('family_name')),
            has_picture=bool(idinfo.get('picture'))
        )
        
        return idinfo
        
    except ValueError as e:
        logger.error(
            "Google token validation failed - ValueError",
            function="validate_google_authentication",
            error=str(e),
            error_type=type(e).__name__,
            id_token_preview=id_token_preview
        )
        raise CatenException(
            error_code="AUTH_002",
            error_message="Invalid Google ID token",
            status_code=401,
            details={"error": str(e)}
        )
    except CatenException:
        # Re-raise CatenException without modification
        raise
    except Exception as e:
        logger.error(
            "Unexpected error during Google token validation",
            function="validate_google_authentication",
            error=str(e),
            error_type=type(e).__name__,
            id_token_preview=id_token_preview
        )
        raise CatenException(
            error_code="AUTH_003",
            error_message="Token validation error",
            status_code=401,
            details={"error": str(e)}
        )

