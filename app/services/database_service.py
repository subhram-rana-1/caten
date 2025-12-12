"""Database service for user and session management."""

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
import secrets
import uuid
import structlog
import json

from app.config import settings
from app.services.in_memory_cache.cache_factory import get_in_memory_cache

logger = structlog.get_logger()


def get_or_create_user_by_google_sub(
    db: Session,
    sub: str,
    google_data: dict
) -> Tuple[str, str, bool]:
    """
    Get or create user and google_user_auth_info records.
    
    Args:
        db: Database session
        sub: Google user ID (sub field)
        google_data: Decoded Google token data
        
    Returns:
        Tuple of (user_id, google_auth_info_id, is_new_user)
    """
    # Entry log
    logger.info(
        "Getting or creating user by Google sub",
        function="get_or_create_user_by_google_sub",
        sub=sub,
        has_email=bool(google_data.get("email")),
        email_verified=google_data.get("email_verified", False)
    )
    
    # Check if sub exists in google_user_auth_info
    logger.debug(
        "Querying database for existing user by sub",
        function="get_or_create_user_by_google_sub",
        sub=sub
    )
    result = db.execute(
        text("SELECT id, user_id FROM google_user_auth_info WHERE sub = :sub"),
        {"sub": sub}
    ).fetchone()
    
    if result:
        # User exists, update google_user_auth_info
        google_auth_info_id = result[0]
        user_id = result[1]
        is_new_user = False
        
        logger.debug(
            "Existing user found, updating google_user_auth_info",
            function="get_or_create_user_by_google_sub",
            sub=sub,
            user_id=user_id,
            google_auth_info_id=google_auth_info_id
        )
        
        # Update google_user_auth_info
        db.execute(
            text("""
                UPDATE google_user_auth_info 
                SET iss = :iss, email = :email, email_verified = :email_verified,
                    given_name = :given_name, family_name = :family_name,
                    picture = :picture, locale = :locale, azp = :azp,
                    aud = :aud, iat = :iat, exp = :exp, jti = :jti,
                    alg = :alg, kid = :kid, typ = :typ, hd = :hd,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
            """),
            {
                "id": google_auth_info_id,
                "iss": google_data.get("iss"),
                "email": google_data.get("email"),
                "email_verified": google_data.get("email_verified", False),
                "given_name": google_data.get("given_name"),
                "family_name": google_data.get("family_name"),
                "picture": google_data.get("picture"),
                "locale": google_data.get("locale"),
                "azp": google_data.get("azp"),
                "aud": google_data.get("aud"),
                "iat": str(google_data.get("iat", "")),
                "exp": str(google_data.get("exp", "")),
                "jti": google_data.get("jti"),
                "alg": google_data.get("alg"),
                "kid": google_data.get("kid"),
                "typ": google_data.get("typ"),
                "hd": google_data.get("hd")
            }
        )
        
        logger.info(
            "Updated existing user",
            function="get_or_create_user_by_google_sub",
            user_id=user_id,
            google_auth_info_id=google_auth_info_id,
            sub=sub
        )
    else:
        # New user, create records
        is_new_user = True
        
        logger.debug(
            "No existing user found, creating new user",
            function="get_or_create_user_by_google_sub",
            sub=sub
        )
        
        # Generate user_id
        user_id = str(uuid.uuid4())
        
        logger.debug(
            "Creating user record",
            function="get_or_create_user_by_google_sub",
            user_id=user_id,
            sub=sub
        )
        
        # Create user record
        db.execute(
            text("INSERT INTO user (id) VALUES (:user_id)"),
            {"user_id": user_id}
        )
        db.flush()
        
        # Generate google_auth_info_id
        google_auth_info_id = str(uuid.uuid4())
        
        logger.debug(
            "Creating google_user_auth_info record",
            function="get_or_create_user_by_google_sub",
            user_id=user_id,
            google_auth_info_id=google_auth_info_id,
            sub=sub
        )
        
        # Create google_user_auth_info record
        db.execute(
            text("""
                INSERT INTO google_user_auth_info 
                (id, user_id, iss, sub, email, email_verified, given_name, family_name,
                 picture, locale, azp, aud, iat, exp, jti, alg, kid, typ, hd)
                VALUES 
                (:id, :user_id, :iss, :sub, :email, :email_verified, :given_name,
                 :family_name, :picture, :locale, :azp, :aud, :iat, :exp, :jti,
                 :alg, :kid, :typ, :hd)
            """),
            {
                "id": google_auth_info_id,
                "user_id": user_id,
                "iss": google_data.get("iss"),
                "sub": sub,
                "email": google_data.get("email"),
                "email_verified": google_data.get("email_verified", False),
                "given_name": google_data.get("given_name"),
                "family_name": google_data.get("family_name"),
                "picture": google_data.get("picture"),
                "locale": google_data.get("locale"),
                "azp": google_data.get("azp"),
                "aud": google_data.get("aud"),
                "iat": str(google_data.get("iat", "")),
                "exp": str(google_data.get("exp", "")),
                "jti": google_data.get("jti"),
                "alg": google_data.get("alg"),
                "kid": google_data.get("kid"),
                "typ": google_data.get("typ"),
                "hd": google_data.get("hd")
            }
        )
        db.flush()
        
        logger.info(
            "Created new user",
            function="get_or_create_user_by_google_sub",
            user_id=user_id,
            google_auth_info_id=google_auth_info_id,
            sub=sub,
            email=google_data.get("email")
        )
    
    db.commit()
    
    logger.info(
        "User lookup/creation completed",
        function="get_or_create_user_by_google_sub",
        user_id=user_id,
        google_auth_info_id=google_auth_info_id,
        is_new_user=is_new_user,
        sub=sub
    )
    
    return user_id, google_auth_info_id, is_new_user


def get_or_create_user_session(
    db: Session,
    auth_vendor_type: str,
    auth_vendor_id: str,
    is_new_user: bool
) -> Tuple[str, str, datetime]:
    """
    Get or create user session and update refresh token.
    
    Args:
        db: Database session
        auth_vendor_type: Authentication vendor type (e.g., 'GOOGLE')
        auth_vendor_id: Primary key of google_user_auth_info
        is_new_user: Whether this is a new user
        
    Returns:
        Tuple of (session_id, refresh_token, refresh_token_expires_at)
    """
    # Entry log
    logger.info(
        "Getting or creating user session",
        function="get_or_create_user_session",
        auth_vendor_type=auth_vendor_type,
        auth_vendor_id=auth_vendor_id,
        is_new_user=is_new_user
    )
    
    # Generate new refresh token
    refresh_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expiry_days)
    access_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.access_token_expiry_hours)
    
    refresh_token_preview = refresh_token[:8] + "..." if refresh_token else None
    logger.debug(
        "Refresh token generated",
        function="get_or_create_user_session",
        refresh_token_preview=refresh_token_preview,
        expires_at=str(expires_at)
    )
    
    if is_new_user:
        # Generate session_id
        session_id = str(uuid.uuid4())
        
        logger.debug(
            "Creating new session for new user",
            function="get_or_create_user_session",
            session_id=session_id,
            auth_vendor_type=auth_vendor_type,
            auth_vendor_id=auth_vendor_id
        )
        
        # Create new session
        db.execute(
            text("""
                INSERT INTO user_session 
                (id, auth_vendor_type, auth_vendor_id, access_token_state,
                 refresh_token, refresh_token_expires_at, access_token_expires_at)
                VALUES 
                (:id, :auth_vendor_type, :auth_vendor_id, 'VALID',
                 :refresh_token, :refresh_token_expires_at, :access_token_expires_at)
            """),
            {
                "id": session_id,
                "auth_vendor_type": auth_vendor_type,
                "auth_vendor_id": auth_vendor_id,
                "refresh_token": refresh_token,
                "refresh_token_expires_at": expires_at,
                "access_token_expires_at": access_token_expires_at
            }
        )
        db.flush()
        
        logger.info(
            "Created new session",
            function="get_or_create_user_session",
            session_id=session_id,
            auth_vendor_type=auth_vendor_type,
            auth_vendor_id=auth_vendor_id
        )
    else:
        # Update existing session
        logger.debug(
            "Looking up existing session for user",
            function="get_or_create_user_session",
            auth_vendor_type=auth_vendor_type,
            auth_vendor_id=auth_vendor_id
        )
        session_result = db.execute(
            text("""
                SELECT id FROM user_session 
                WHERE auth_vendor_type = :auth_vendor_type 
                AND auth_vendor_id = :auth_vendor_id
                ORDER BY updated_at DESC LIMIT 1
            """),
            {
                "auth_vendor_type": auth_vendor_type,
                "auth_vendor_id": auth_vendor_id
            }
        ).fetchone()
        
        if session_result:
            session_id = session_result[0]
            logger.debug(
                "Existing session found, updating",
                function="get_or_create_user_session",
                session_id=session_id,
                auth_vendor_type=auth_vendor_type,
                auth_vendor_id=auth_vendor_id
            )
            # Update session
            db.execute(
                text("""
                    UPDATE user_session 
                    SET access_token_state = 'VALID',
                        refresh_token = :refresh_token,
                        refresh_token_expires_at = :refresh_token_expires_at,
                        access_token_expires_at = :access_token_expires_at,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :session_id
                """),
                {
                    "session_id": session_id,
                    "refresh_token": refresh_token,
                    "refresh_token_expires_at": expires_at,
                    "access_token_expires_at": access_token_expires_at
                }
            )
            logger.info(
                "Updated existing session",
                function="get_or_create_user_session",
                session_id=session_id,
                auth_vendor_type=auth_vendor_type,
                auth_vendor_id=auth_vendor_id
            )
        else:
            # No session found, create one
            session_id = str(uuid.uuid4())
            
            logger.debug(
                "No existing session found, creating new session",
                function="get_or_create_user_session",
                session_id=session_id,
                auth_vendor_type=auth_vendor_type,
                auth_vendor_id=auth_vendor_id
            )
            
            db.execute(
                text("""
                    INSERT INTO user_session 
                    (id, auth_vendor_type, auth_vendor_id, access_token_state,
                     refresh_token, refresh_token_expires_at, access_token_expires_at)
                    VALUES 
                    (:id, :auth_vendor_type, :auth_vendor_id, 'VALID',
                     :refresh_token, :refresh_token_expires_at, :access_token_expires_at)
                """),
                {
                    "id": session_id,
                    "auth_vendor_type": auth_vendor_type,
                    "auth_vendor_id": auth_vendor_id,
                    "refresh_token": refresh_token,
                    "refresh_token_expires_at": expires_at,
                    "access_token_expires_at": access_token_expires_at
                }
            )
            db.flush()
            logger.info(
                "Created new session for existing user",
                function="get_or_create_user_session",
                session_id=session_id,
                auth_vendor_type=auth_vendor_type,
                auth_vendor_id=auth_vendor_id
            )
    
    db.commit()
    
    logger.info(
        "User session operation completed",
        function="get_or_create_user_session",
        session_id=session_id,
        auth_vendor_type=auth_vendor_type,
        refresh_token_preview=refresh_token_preview,
        expires_at=str(expires_at)
    )
    
    return session_id, refresh_token, expires_at


def invalidate_user_session(
    db: Session,
    auth_vendor_type: str,
    sub: str
) -> bool:
    """
    Invalidate user session by marking access_token_state as INVALID.
    
    Args:
        db: Database session
        auth_vendor_type: Authentication vendor type (e.g., 'GOOGLE')
        sub: Google user ID (sub field)
        
    Returns:
        True if session was found and invalidated, False otherwise
    """
    # Entry log
    logger.info(
        "Invalidating user session",
        function="invalidate_user_session",
        auth_vendor_type=auth_vendor_type,
        sub=sub
    )
    
    # First, get the google_auth_info_id from sub
    logger.debug(
        "Looking up google_auth_info_id by sub",
        function="invalidate_user_session",
        sub=sub
    )
    google_auth_result = db.execute(
        text("SELECT id FROM google_user_auth_info WHERE sub = :sub"),
        {"sub": sub}
    ).fetchone()
    
    if not google_auth_result:
        logger.warning(
            "No google_auth_info found for sub",
            function="invalidate_user_session",
            sub=sub,
            auth_vendor_type=auth_vendor_type
        )
        return False
    
    google_auth_info_id = google_auth_result[0]
    
    logger.debug(
        "Google auth info found, invalidating session",
        function="invalidate_user_session",
        sub=sub,
        google_auth_info_id=google_auth_info_id,
        auth_vendor_type=auth_vendor_type
    )
    
    # Update the session to mark it as INVALID
    result = db.execute(
        text("""
            UPDATE user_session 
            SET access_token_state = 'INVALID',
                updated_at = CURRENT_TIMESTAMP
            WHERE auth_vendor_type = :auth_vendor_type 
            AND auth_vendor_id = :auth_vendor_id
            AND access_token_state = 'VALID'
        """),
        {
            "auth_vendor_type": auth_vendor_type,
            "auth_vendor_id": google_auth_info_id
        }
    )
    
    db.commit()
    
    if result.rowcount > 0:
        logger.info(
            "Session invalidated successfully",
            function="invalidate_user_session",
            auth_vendor_type=auth_vendor_type,
            sub=sub,
            google_auth_info_id=google_auth_info_id,
            rows_updated=result.rowcount
        )
        return True
    else:
        logger.warning(
            "No valid session found to invalidate",
            function="invalidate_user_session",
            auth_vendor_type=auth_vendor_type,
            sub=sub,
            google_auth_info_id=google_auth_info_id,
            rows_updated=result.rowcount
        )
        return False


def get_user_info_by_sub(
    db: Session,
    sub: str
) -> Optional[dict]:
    """
    Get user information by Google sub.
    
    Args:
        db: Database session
        sub: Google user ID (sub field)
        
    Returns:
        Dictionary with user information (user_id, name, first_name, last_name, email, picture)
        or None if user not found
    """
    # Entry log
    logger.info(
        "Getting user info by sub",
        function="get_user_info_by_sub",
        sub=sub
    )
    
    logger.debug(
        "Querying database for user info",
        function="get_user_info_by_sub",
        sub=sub
    )
    result = db.execute(
        text("""
            SELECT 
                u.id as user_id,
                g.given_name,
                g.family_name,
                g.email,
                g.picture
            FROM google_user_auth_info g
            INNER JOIN user u ON g.user_id = u.id
            WHERE g.sub = :sub
        """),
        {"sub": sub}
    ).fetchone()
    
    if not result:
        logger.warning(
            "User not found for sub",
            function="get_user_info_by_sub",
            sub=sub
        )
        return None
    
    user_id, given_name, family_name, email, picture = result
    
    # Construct full name
    name_parts = []
    if given_name:
        name_parts.append(given_name)
    if family_name:
        name_parts.append(family_name)
    name = " ".join(name_parts).strip() if name_parts else ""
    
    logger.info(
        "User info retrieved successfully",
        function="get_user_info_by_sub",
        user_id=user_id,
        sub=sub,
        email=email,
        has_name=bool(name),
        has_picture=bool(picture)
    )
    
    return {
        "user_id": user_id,
        "name": name,
        "first_name": given_name,
        "last_name": family_name,
        "email": email,
        "picture": picture
    }


def get_unauthenticated_user_usage(
    db: Session,
    user_id: str
) -> Optional[Dict[str, Any]]:
    """
    Get unauthenticated user API usage record.
    
    Args:
        db: Database session
        user_id: Unauthenticated user ID (UUID)
        
    Returns:
        Dictionary with api_usage JSON data or None if not found
    """
    result = db.execute(
        text("SELECT api_usage FROM unauthenticated_user_api_usage WHERE user_id = :user_id"),
        {"user_id": user_id}
    ).fetchone()
    
    if not result:
        return None
    
    api_usage_json = result[0]
    if isinstance(api_usage_json, str):
        api_usage = json.loads(api_usage_json)
    else:
        api_usage = api_usage_json
    
    return api_usage


def create_unauthenticated_user_usage(
    db: Session,
    api_name: str
) -> str:
    """
    Create a new unauthenticated user API usage record.
    
    Args:
        db: Database session
        api_name: Name of the API being called (used to initialize counter)
        
    Returns:
        Newly created user_id (UUID)
    """
    user_id = str(uuid.uuid4())
    
    # Initialize API usage JSON with all counters set to 0
    api_usage = {
        "words_explanation_api_count_so_far": 0,
        "get_more_explanations_api_count_so_far": 0,
        "ask_api_count_so_far": 0,
        "simplify_api_count_so_far": 0,
        "summarise_api_count_so_far": 0,
        "image_to_text_api_count_so_far": 0,
        "pdf_to_text_api_count_so_far": 0,
        "important_words_from_text_v1_api_count_so_far": 0,
        "words_explanation_v1_api_count_so_far": 0,
        "get_random_paragraph_api_count_so_far": 0,
        "important_words_from_text_v2_api_count_so_far": 0,
        "pronunciation_api_count_so_far": 0,
        "voice_to_text_api_count_so_far": 0,
        "translate_api_count_so_far": 0,
        "web_search_api_count_so_far": 0,
        "web_search_stream_api_count_so_far": 0
    }
    
    # Set the current API count to 1 (this API was just called)
    if api_name in api_usage:
        api_usage[api_name] = 1
    else:
        # If api_name is not in the dictionary, add it and set to 1
        logger.warning(
            "API name not found in api_usage dictionary, adding it",
            api_name=api_name
        )
        api_usage[api_name] = 1
    
    db.execute(
        text("""
            INSERT INTO unauthenticated_user_api_usage 
            (user_id, api_usage)
            VALUES 
            (:user_id, :api_usage)
        """),
        {
            "user_id": user_id,
            "api_usage": json.dumps(api_usage)
        }
    )
    db.commit()
    
    logger.info("Created unauthenticated user API usage record", user_id=user_id, api_name=api_name)
    return user_id


def increment_api_usage(
    db: Session,
    user_id: str,
    api_name: str
) -> None:
    """
    Increment the API usage counter for a specific API.
    
    Args:
        db: Database session
        user_id: Unauthenticated user ID (UUID)
        api_name: Name of the API counter field to increment
    """
    # Get current usage
    result = db.execute(
        text("SELECT api_usage FROM unauthenticated_user_api_usage WHERE user_id = :user_id"),
        {"user_id": user_id}
    ).fetchone()
    
    if not result:
        logger.warning("Unauthenticated user usage record not found", user_id=user_id)
        return
    
    api_usage_json = result[0]
    if isinstance(api_usage_json, str):
        api_usage = json.loads(api_usage_json)
    else:
        api_usage = api_usage_json
    
    # Increment the counter
    if api_name in api_usage:
        api_usage[api_name] = api_usage.get(api_name, 0) + 1
    else:
        api_usage[api_name] = 1
    
    # Update the record
    db.execute(
        text("""
            UPDATE unauthenticated_user_api_usage 
            SET api_usage = :api_usage,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = :user_id
        """),
        {
            "user_id": user_id,
            "api_usage": json.dumps(api_usage)
        }
    )
    db.commit()
    
    logger.info("Incremented API usage", user_id=user_id, api_name=api_name, count=api_usage[api_name])


def check_api_usage_limit(
    db: Session,
    user_id: str,
    api_name: str,
    max_limit: int
) -> bool:
    """
    Check if API usage has exceeded the maximum limit.
    
    Args:
        db: Database session
        user_id: Unauthenticated user ID (UUID)
        api_name: Name of the API counter field to check
        max_limit: Maximum allowed usage count
        
    Returns:
        True if limit is exceeded, False otherwise
    """
    api_usage = get_unauthenticated_user_usage(db, user_id)
    
    if not api_usage:
        return True  # No record found, consider as limit exceeded
    
    current_count = api_usage.get(api_name, 0)
    return current_count >= max_limit


def get_user_session_by_id(
    db: Session,
    session_id: str
) -> Optional[Dict[str, Any]]:
    """
    Get user session by session ID.
    
    Args:
        db: Database session
        session_id: User session ID (primary key)
        
    Returns:
        Dictionary with session data or None if not found
    """
    # Get cache instance
    cache = get_in_memory_cache()
    cache_key = f"USER_SESSION_INFO:{session_id}"
    
    # Check cache first
    cached_session = cache.get_key(cache_key)
    if cached_session is not None:
        return cached_session
    
    result = db.execute(
        text("""
            SELECT id, auth_vendor_type, auth_vendor_id, access_token_state,
                   refresh_token, refresh_token_expires_at, access_token_expires_at
            FROM user_session 
            WHERE id = :session_id
        """),
        {"session_id": session_id}
    ).fetchone()
    
    if not result:
        return None
    
    session_data = {
        "id": result[0],
        "auth_vendor_type": result[1],
        "auth_vendor_id": result[2],
        "access_token_state": result[3],
        "refresh_token": result[4],
        "refresh_token_expires_at": result[5],
        "access_token_expires_at": result[6]
    }
    
    # Store in cache before returning
    cache.set_key(cache_key, session_data)

    return session_data


def update_user_session_refresh_token(
    db: Session,
        session_id: str,
    access_token_expires_at: Optional[datetime] = None
) -> Tuple[str, datetime]:
    """
    Update refresh token and expiry for a user session.
    Also updates access_token_expires_at and sets access_token_state to VALID if access_token_expires_at is provided.
    
    Args:
        db: Database session
        session_id: User session ID (primary key)
        access_token_expires_at: Optional access token expiry datetime. If provided, also updates access_token_expires_at and sets access_token_state to 'VALID'
        
    Returns:
        Tuple of (new_refresh_token, new_refresh_token_expires_at)
    """
    # Entry log
    logger.info(
        "Updating user session refresh token",
        function="update_user_session_refresh_token",
        session_id=session_id
    )
    
    # Generate new refresh token
    refresh_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    
    refresh_token_preview = refresh_token[:8] + "..." if refresh_token else None
    logger.debug(
        "New refresh token generated",
        function="update_user_session_refresh_token",
        session_id=session_id,
        refresh_token_preview=refresh_token_preview,
        expires_at=str(expires_at)
    )
    
    # Update the session
    logger.debug(
        "Updating session in database",
        function="update_user_session_refresh_token",
        session_id=session_id,
        has_access_token_expires_at=access_token_expires_at is not None
    )
    
    # Build SQL query based on whether access_token_expires_at is provided
    if access_token_expires_at:
        db.execute(
            text("""
                UPDATE user_session 
                SET refresh_token = :refresh_token,
                    refresh_token_expires_at = :refresh_token_expires_at,
                    access_token_expires_at = :access_token_expires_at,
                    access_token_state = 'VALID',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :session_id
            """),
            {
                "session_id": session_id,
                "refresh_token": refresh_token,
                "refresh_token_expires_at": expires_at,
                "access_token_expires_at": access_token_expires_at
            }
        )
    else:
        db.execute(
            text("""
                UPDATE user_session 
                SET refresh_token = :refresh_token,
                    refresh_token_expires_at = :refresh_token_expires_at,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :session_id
            """),
            {
                "session_id": session_id,
                "refresh_token": refresh_token,
                "refresh_token_expires_at": expires_at
            }
        )
    
    db.commit()
    
    logger.info(
        "Refresh token updated successfully",
        function="update_user_session_refresh_token",
        session_id=session_id,
        refresh_token_preview=refresh_token_preview,
        expires_at=str(expires_at)
    )
    
    return refresh_token, expires_at

