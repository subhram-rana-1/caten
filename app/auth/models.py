"""SQLAlchemy Core table definitions for authentication and session management."""

from datetime import datetime
from sqlalchemy import (
    Table,
    Column,
    Integer,
    String,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
    MetaData,
    Index,
)
from sqlalchemy.sql import func

# Metadata for async SQLAlchemy
metadata = MetaData()

# Users table
users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("google_sub", String(255), unique=True, nullable=False, index=True),
    Column("email", String(320), nullable=False, unique=True, index=True),
    Column("name", String(255), nullable=True),
    Column("picture_url", Text, nullable=True),
    Column("created_at", DateTime, server_default=func.now(), nullable=False),
    Column("last_login_at", DateTime, nullable=True),
    Column("is_active", Boolean, default=True, nullable=False, index=True),
    Index("idx_users_google_sub", "google_sub"),
    Index("idx_users_email", "email"),
    Index("idx_users_is_active", "is_active"),
)

# Refresh tokens table
refresh_tokens = Table(
    "refresh_tokens",
    metadata,
    Column("id", String(36), primary_key=True),  # UUID stored as CHAR(36)
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("token_hash", String(255), nullable=False, index=True),
    Column("device_id", String(128), nullable=False, index=True),
    Column("issued_at", DateTime, server_default=func.now(), nullable=False),
    Column("expires_at", DateTime, nullable=False),
    Column("revoked_at", DateTime, nullable=True, index=True),
    Column("last_used_at", DateTime, nullable=True),
    Index("idx_refresh_tokens_user_id", "user_id"),
    Index("idx_refresh_tokens_device_id", "device_id"),
    Index("idx_refresh_tokens_token_hash", "token_hash"),
    Index("idx_refresh_tokens_expires_at", "expires_at"),
    Index("idx_refresh_tokens_revoked_at", "revoked_at"),
)

# Unauthenticated device requests table
unauth_device_requests = Table(
    "unauth_device_requests",
    metadata,
    Column("device_id", String(128), primary_key=True),
    Column("request_count", Integer, nullable=False, server_default="0"),
    Column("first_seen", DateTime, server_default=func.now(), nullable=False),
    Column("last_request_at", DateTime, server_default=func.now(), onupdate=func.now(), nullable=False, index=True),
    Index("idx_unauth_device_requests_last_request_at", "last_request_at"),
)
