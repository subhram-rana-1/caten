-- Authentication and Session Management Database Schema
-- MariaDB database schema for users, refresh tokens, and unauthenticated device requests

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    google_sub VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(320) NOT NULL,
    name VARCHAR(255),
    picture_url TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    last_login_at DATETIME NULL,
    is_active BOOLEAN DEFAULT TRUE,
    CONSTRAINT users_email_unique UNIQUE (email)
) COMMENT='User accounts created from Google ID tokens';

-- Indexes for users table
CREATE INDEX IF NOT EXISTS idx_users_google_sub ON users(google_sub);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);

-- Refresh tokens table
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id CHAR(36) PRIMARY KEY,
    user_id INT NOT NULL,
    token_hash VARCHAR(255) NOT NULL,
    device_id VARCHAR(128) NOT NULL,
    issued_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    expires_at DATETIME NOT NULL,
    revoked_at DATETIME NULL,
    last_used_at DATETIME NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_refresh_tokens_user_id (user_id),
    INDEX idx_refresh_tokens_device_id (device_id),
    INDEX idx_refresh_tokens_token_hash (token_hash),
    INDEX idx_refresh_tokens_expires_at (expires_at),
    INDEX idx_refresh_tokens_revoked_at (revoked_at),
    INDEX idx_refresh_tokens_device_revoked_expires (device_id, revoked_at, expires_at),
    INDEX idx_refresh_tokens_user_revoked (user_id, revoked_at)
) COMMENT='Hashed refresh tokens for session management';

-- Unauthenticated device requests table
CREATE TABLE IF NOT EXISTS unauth_device_requests (
    device_id VARCHAR(128) PRIMARY KEY,
    request_count INT NOT NULL DEFAULT 0,
    first_seen DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    last_request_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP NOT NULL
) COMMENT='Track unauthenticated request counts per device';

-- Index for unauth_device_requests table (primary key already indexed)
CREATE INDEX IF NOT EXISTS idx_unauth_device_requests_last_request_at ON unauth_device_requests(last_request_at);
