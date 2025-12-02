"""Configuration management for the FastAPI application."""

from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Ignore extra fields from environment variables
    )
    
    # OpenAI Configuration
    openai_api_key: str = Field(..., description="OpenAI API key")
    
    # Server Configuration
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    
    # Rate Limiting Configuration
    enable_rate_limiting: bool = Field(default=True, description="Enable rate limiting")
    rate_limit_requests_per_window: int = Field(default=10, description="Maximum number of requests allowed per time window")
    rate_limit_window_size_seconds: int = Field(default=10, description="Time window size in seconds for rate limiting")
    
    # File Upload Configuration
    max_file_size_mb: int = Field(default=2, description="Maximum file size in MB")
    allowed_image_types: str = Field(default="jpeg,jpg,png,heic", description="Allowed image types")
    allowed_pdf_types: str = Field(default="pdf", description="Allowed PDF types")
    
    @property
    def allowed_image_types_list(self) -> List[str]:
        """Get allowed image types as a list."""
        return [ext.strip().lower() for ext in self.allowed_image_types.split(",")]
    
    @property
    def allowed_pdf_types_list(self) -> List[str]:
        """Get allowed PDF types as a list."""
        return [ext.strip().lower() for ext in self.allowed_pdf_types.split(",")]
    
    @property
    def max_file_size_bytes(self) -> int:
        """Get maximum file size in bytes."""
        return self.max_file_size_mb * 1024 * 1024
    
    # LLM Configuration
    gpt4_turbo_model: str = Field(default="gpt-4-turbo-2024-04-09", description="GPT-4 Turbo model name")
    gpt4o_model: str = Field(default="gpt-4o", description="GPT-4o model name")
    max_tokens: int = Field(default=2000, description="Maximum tokens for LLM responses")
    temperature: float = Field(default=0.7, description="Temperature for LLM responses")
    
    # Tesseract Configuration
    tesseract_cmd: str = Field(default="/usr/bin/tesseract", description="Tesseract command path")
    
    # Random Paragraph Configuration
    random_paragraph_word_count: int = Field(default=50, description="Number of words in random paragraph")
    random_paragraph_difficulty_percentage: int = Field(default=60, description="Percentage of difficult words in random paragraph")
    
    # Text Simplification Configuration
    max_simplification_attempts: int = Field(default=1, description="Maximum number of simplification attempts allowed")
    
    # More Examples Configuration
    more_examples_threshold: int = Field(default=2, description="Maximum number of examples to allow fetching more examples")
    
    # Monitoring
    enable_metrics: bool = Field(default=True, description="Enable Prometheus metrics")
    metrics_port: int = Field(default=9090, description="Metrics server port")
    
    # Authentication Configuration
    google_client_id: str = Field(..., description="Google OAuth 2.0 Client ID for ID token verification")
    jwt_secret: str = Field(..., description="Secret key for JWT signing (HS256) or private key path (RS256)")
    jwt_algorithm: str = Field(default="HS256", description="JWT signing algorithm (HS256 or RS256)")
    access_token_expire_minutes: int = Field(default=15, description="Access token expiration time in minutes")
    refresh_token_expire_days: int = Field(default=30, description="Refresh token expiration time in days")
    unauthenticated_device_max_request_count: int = Field(default=20, description="Maximum unauthenticated requests allowed per device")
    
    # Database Configuration
    database_url: str = Field(..., description="MariaDB database connection URL (mariadb+aiomysql://user:password@localhost:3306/dbname)")
    database_pool_size: int = Field(default=10, description="Database connection pool size")
    database_max_overflow: int = Field(default=20, description="Maximum database connection pool overflow")


# Global settings instance
settings = Settings()
