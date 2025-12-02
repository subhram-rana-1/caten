"""Google ID token verification using google-auth library."""

from typing import Dict, Any
from google.oauth2 import id_token
from google.auth.transport import requests
import structlog

logger = structlog.get_logger()


async def verify_google_id_token(id_token_str: str, client_id: str) -> Dict[str, Any]:
    """
    Verify Google ID token and return decoded payload.
    
    Args:
        id_token_str: Google ID token JWT string
        client_id: Google OAuth 2.0 Client ID to verify against
        
    Returns:
        Dictionary containing verified token claims (sub, email, name, picture, etc.)
        
    Raises:
        ValueError: If token is invalid, expired, or audience doesn't match
        Exception: For other verification errors
    """
    try:
        # Create a requests session for token verification
        request = requests.Request()
        
        # Verify the token
        # This will:
        # 1. Verify the token signature using Google's public keys
        # 2. Verify the token hasn't expired
        # 3. Verify the audience (aud) claim matches client_id
        # 4. Download and cache Google's public keys if needed
        token_info = id_token.verify_oauth2_token(
            id_token_str,
            request,
            client_id
        )
        
        # Verify that the token has required claims
        if "sub" not in token_info:
            raise ValueError("Token missing 'sub' claim")
        
        if "email" not in token_info:
            raise ValueError("Token missing 'email' claim")
        
        logger.info(
            "Google ID token verified successfully",
            sub=token_info.get("sub"),
            email=token_info.get("email")
        )
        
        return token_info
        
    except ValueError as e:
        logger.warning("Google ID token verification failed", error=str(e))
        raise ValueError(f"Invalid Google token: {str(e)}")
    except Exception as e:
        logger.error("Unexpected error during Google token verification", error=str(e), error_type=type(e).__name__)
        raise Exception(f"Token verification error: {str(e)}")




