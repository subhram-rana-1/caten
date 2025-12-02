"""Pydantic schemas for authentication requests and responses."""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class ErrorResponse(BaseModel):
    """Standard error response schema."""
    
    error_code: str = Field(..., description="Machine-readable error code")
    error_reason: str = Field(..., description="Human-readable error reason")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error details")


class GoogleLoginRequest(BaseModel):
    """Request schema for Google ID token login."""
    
    id_token: str = Field(..., description="Google ID token JWT")
    device_id: str = Field(..., description="Device identifier (UUID)")
    device_info: Optional[str] = Field(default=None, description="Optional device information string")


class RefreshTokenRequest(BaseModel):
    """Request schema for refresh token endpoint."""
    
    refresh_token: str = Field(..., description="Opaque refresh token")
    device_id: str = Field(..., description="Device identifier (UUID)")


class LogoutRequest(BaseModel):
    """Request schema for logout endpoint."""
    
    revoke_all: bool = Field(default=False, description="Revoke all refresh tokens for user (not just current device)")


class UserResponse(BaseModel):
    """User information response schema."""
    
    id: int = Field(..., description="User ID")
    email: str = Field(..., description="User email address")
    name: Optional[str] = Field(default=None, description="User display name")
    picture_url: Optional[str] = Field(default=None, description="User profile picture URL")
    
    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """Token response schema for login and refresh endpoints."""
    
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration time in seconds")
    refresh_token: Optional[str] = Field(default=None, description="Opaque refresh token (only on login/refresh)")
    user: Optional[UserResponse] = Field(default=None, description="User information (only on login)")


class LogoutResponse(BaseModel):
    """Logout response schema."""
    
    ok: bool = Field(default=True, description="Logout success status")


class ProfileResponse(BaseModel):
    """User profile response schema."""
    
    id: int = Field(..., description="User ID")
    email: str = Field(..., description="User email address")
    name: Optional[str] = Field(default=None, description="User display name")
    picture_url: Optional[str] = Field(default=None, description="User profile picture URL")
    created_at: str = Field(..., description="Account creation timestamp (ISO format)")
    last_login_at: Optional[str] = Field(default=None, description="Last login timestamp (ISO format)")
    is_active: bool = Field(..., description="Account active status")
    
    model_config = ConfigDict(from_attributes=True)




