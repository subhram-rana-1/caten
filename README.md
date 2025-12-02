# Caten API

A FastAPI-based backend server for text and image processing with LLM integration. The API provides endpoints for extracting text from images, analyzing important words, and generating contextual explanations.

## Features

- **Image to Text**: Extract readable text from images using GPT-4 Turbo with Vision
- **PDF to Text**: Extract readable text from PDF files and return in markdown format
- **Important Words Analysis**: Identify the most important/difficult words in text
- **Word Explanations**: Get contextual meanings and examples with SSE streaming
- **Additional Examples**: Generate more simplified examples for words
- **Rate Limiting**: Configurable rate limiting with Redis
- **Monitoring**: Prometheus metrics and structured logging
- **Production Ready**: Docker support, health checks, and proper error handling

## API Endpoints

### 1. Extract Text from Image
- **POST** `/api/v1/image-to-text`
- Upload an image file (JPEG, JPG, PNG, HEIC) to extract text
- Maximum file size: 5MB
- Handles rotated/tilted images and transparent overlays

### 2. Extract Text from PDF
- **POST** `/api/v1/pdf-to-text`
- Upload a PDF file to extract text in markdown format
- Maximum file size: 2MB
- Supports multi-page PDFs with proper formatting
- Returns structured markdown content

### 3. Get Important Words
- **POST** `/api/v1/important-words-from-text`
- Analyze text to find the top 10 most important/difficult words
- Returns word positions in the original text

### 4. Get Word Explanations (Streaming)
- **POST** `/api/v1/words-explanation`
- Stream contextual meanings and examples via Server-Sent Events
- Concurrent processing for multiple words

### 5. Get More Examples
- **POST** `/api/v1/get-more-explanations`
- Generate additional simplified example sentences for a word

## Quick Start

### Prerequisites

- Python 3.9+
- OpenAI API key
- Redis (for rate limiting)
- Tesseract OCR (for image processing)
- PyPDF2 and pdfplumber (for PDF processing)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd caten
```

2. Create `.env` file with your configuration:
```bash
OPENAI_API_KEY=your_openai_api_key_here
```

4. Run the application:
```bash
./start.sh
```

The API will be available at `http://localhost:8000`

### Using Docker

1. Create `.env` file with your configuration:

2. Run with Docker Compose:
```bash
docker-compose up -d
```

This will start:
- Caten API server on port 8000
- Redis on port 6379
- Prometheus on port 9090
- Grafana on port 3000 (admin/admin)

## Configuration

All configuration is managed through environment variables or the `.env` file:

### Required Settings
- `OPENAI_API_KEY`: Your OpenAI API key

### Optional Settings
- `HOST`: Server host (default: 0.0.0.0)
- `PORT`: Server port (default: 8000)
- `DEBUG`: Enable debug mode (default: False)
- `LOG_LEVEL`: Logging level (default: INFO)
- `ENABLE_RATE_LIMITING`: Enable rate limiting (default: True)
- `RATE_LIMIT_REQUESTS_PER_MINUTE`: Rate limit per minute (default: 60)
- `REDIS_URL`: Redis connection URL (default: redis://localhost:6379)
- `MAX_FILE_SIZE_MB`: Maximum file size in MB (default: 5)
- `ALLOWED_IMAGE_TYPES`: Allowed image types (default: jpeg,jpg,png,heic)

### Authentication Settings (Required for Auth Features)
- `GOOGLE_CLIENT_ID`: Google OAuth 2.0 Client ID for ID token verification (required)
- `JWT_SECRET`: Secret key for JWT signing (HS256) or private key path (RS256) (required)
- `JWT_ALGORITHM`: JWT signing algorithm - HS256 or RS256 (default: HS256)
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Access token expiration time in minutes (default: 15)
- `REFRESH_TOKEN_EXPIRE_DAYS`: Refresh token expiration time in days (default: 30)
- `UNAUTHENTICATED_DEVICE_MAX_REQUEST_COUNT`: Maximum unauthenticated requests per device (default: 20)
- `DATABASE_URL`: MariaDB connection URL (required, format: `mariadb+aiomysql://user:password@localhost:3306/dbname`)
- `DATABASE_POOL_SIZE`: Database connection pool size (default: 10)
- `DATABASE_MAX_OVERFLOW`: Maximum database connection pool overflow (default: 20)

## Authentication & Session Management

The API includes Google ID token-based authentication with JWT access tokens and refresh tokens. All protected endpoints require a valid access token in the `Authorization: Bearer <token>` header.

### Database Setup

1. **Create MariaDB Database**:
```bash
mysql -u root -p -e "CREATE DATABASE xplaino CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

2. **Run Database Migrations**:
```bash
# Using Alembic (recommended)
alembic upgrade head

# Or manually apply schema
mysql -u root -p xplaino < db-schema.sql
```

### Authentication Flow

1. **Login**: Chrome extension obtains Google ID token and sends to `/auth/google`
2. **Token Exchange**: Backend verifies Google token and returns access + refresh tokens
3. **API Access**: Use access token in `Authorization: Bearer <token>` header
4. **Token Refresh**: Exchange refresh token for new access token via `/auth/refresh`
5. **Logout**: Revoke refresh tokens via `/auth/logout`

### Authentication API Endpoints

#### POST /auth/google
Exchange Google ID token for backend session tokens.

**Request**:
```json
{
  "id_token": "<Google ID token JWT>",
  "device_id": "<uuid>",
  "device_info": "<optional string>"
}
```

**Success Response (200)**:
```json
{
  "access_token": "<backend_jwt>",
  "token_type": "bearer",
  "expires_in": 900,
  "refresh_token": "<opaque_refresh_token>",
  "user": {
    "id": 123,
    "email": "user@example.com",
    "name": "User Name",
    "picture_url": "https://..."
  }
}
```

**Error Responses**:
- `400 BAD_REQUEST`: Missing id_token or device_id
  ```json
  {
    "error_code": "BAD_REQUEST",
    "error_reason": "Missing id_token or device_id"
  }
  ```
- `401 UNAUTHORIZED`: Invalid Google token
  ```json
  {
    "error_code": "INVALID_GOOGLE_TOKEN",
    "error_reason": "Google token invalid or expired"
  }
  ```

#### POST /auth/refresh
Exchange refresh token for new access token (with token rotation).

**Request**:
```json
{
  "refresh_token": "<opaque_refresh_token>",
  "device_id": "<uuid>"
}
```

**Success Response (200)**:
```json
{
  "access_token": "<new_backend_jwt>",
  "token_type": "bearer",
  "expires_in": 900,
  "refresh_token": "<new_refresh_token>"
}
```

**Error Responses**:
- `400 BAD_REQUEST`: Malformed request
- `401 UNAUTHORIZED`: Invalid/expired/revoked refresh token
  ```json
  {
    "error_code": "INVALID_REFRESH_TOKEN",
    "error_reason": "Refresh token invalid or revoked"
  }
  ```

#### POST /auth/logout
Revoke refresh tokens for the authenticated user.

**Request** (requires `Authorization: Bearer <access_token>` header):
```json
{
  "revoke_all": false
}
```

**Success Response (200)**:
```json
{
  "ok": true
}
```

**Error Responses**:
- `401 UNAUTHORIZED`: Invalid access token
  ```json
  {
    "error_code": "INVALID_ACCESS_TOKEN",
    "error_reason": "Access token invalid or malformed"
  }
  ```

#### GET /auth/profile
Get current authenticated user's profile.

**Request** (requires `Authorization: Bearer <access_token>` header):
No request body

**Success Response (200)**:
```json
{
  "id": 123,
  "email": "user@example.com",
  "name": "User Name",
  "picture_url": "https://...",
  "created_at": "2024-01-01T00:00:00Z",
  "last_login_at": "2024-01-01T00:00:00Z",
  "is_active": true
}
```

### Device-Based Unauthenticated Request Limits

For endpoints that don't require authentication, the API tracks requests per device:

- Every request must include `X-DEVICE-ID: <device_id>` header (UUID string)
- If `Authorization` header is missing, the backend checks device request count
- Default limit: 20 unauthenticated requests per device (configurable via `UNAUTHENTICATED_DEVICE_MAX_REQUEST_COUNT`)
- If limit exceeded, returns:
  ```json
  {
    "error_code": "TOKEN_NOT_PROVIDED_LIMIT_EXCEEDED",
    "error_reason": "Request token missing and unauthenticated device exceeded allowed anonymous requests"
  }
  ```
- If `Authorization` header is present and token is valid, device counter is not incremented

### Example API Usage

#### 1. Login with Google ID Token
```bash
curl -X POST http://localhost:8000/auth/google \
  -H "Content-Type: application/json" \
  -d '{
    "id_token": "<google_id_token>",
    "device_id": "550e8400-e29b-41d4-a716-446655440000",
    "device_info": "Chrome Extension"
  }'
```

#### 2. Use Access Token for Protected Endpoint
```bash
curl -X GET http://localhost:8000/auth/profile \
  -H "Authorization: Bearer <access_token>" \
  -H "X-DEVICE-ID: 550e8400-e29b-41d4-a716-446655440000"
```

#### 3. Refresh Access Token
```bash
curl -X POST http://localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "<refresh_token>",
    "device_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

#### 4. Logout
```bash
curl -X POST http://localhost:8000/auth/logout \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "revoke_all": false
  }'
```

#### 5. Unauthenticated Request (Device Counting)
```bash
curl -X GET http://localhost:8000/api/v1/some-endpoint \
  -H "X-DEVICE-ID: 550e8400-e29b-41d4-a716-446655440000"
```

### Security Practices

- **Google Token Verification**: Tokens are verified locally using Google's public keys (no external API calls except key downloads)
- **Refresh Token Hashing**: Refresh tokens are hashed (SHA256) before storage; only hashes are stored in database
- **Token Rotation**: Refresh tokens are rotated on each refresh (old token revoked, new token issued)
- **Short-Lived Access Tokens**: Access tokens expire in 15 minutes (configurable)
- **Token Revocation**: Refresh tokens are revoked on logout
- **Device Tracking**: Unauthenticated requests are tracked per device to prevent abuse
- **JWT Signing**: Access tokens are signed with HS256 (configurable to RS256)
- **TLS Required**: All production deployments should use TLS/HTTPS

### Error Codes

Authentication-related error codes:
- `BAD_REQUEST`: Missing required fields in request
- `INVALID_GOOGLE_TOKEN`: Google ID token invalid or expired
- `INVALID_ACCESS_TOKEN`: Access token invalid, malformed, or user not found
- `ACCESS_TOKEN_EXPIRED`: Access token has expired (use refresh endpoint)
- `INVALID_REFRESH_TOKEN`: Refresh token invalid, expired, or revoked
- `TOKEN_NOT_PROVIDED_LIMIT_EXCEEDED`: Unauthenticated device exceeded request limit
- `INTERNAL_ERROR`: Internal server error

## Development

### Running Tests

```bash
# Install development dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest tests/ -v
```

### Code Quality

```bash
# Format code
black app/ tests/

# Lint code
flake8 app/ tests/

# Type checking
mypy app/
```

### API Documentation

When running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Monitoring

### Health Check
- `GET /health`: Service health status

### Metrics
- `GET /metrics`: Prometheus metrics (if enabled)

### Logs
Structured JSON logs are written to stdout and can be collected by your logging infrastructure.

## Error Handling

All APIs return standardized error responses:

```json
{
  "error_code": "ERROR_CODE",
  "error_message": "Human readable error message"
}
```

Common error codes:
- `VAL_001`: Validation error
- `FILE_001`: File validation error
- `IMG_001`: Image processing error
- `LLM_001`: LLM service error
- `RATE_001`: Rate limit exceeded

## Architecture

```
app/
├── main.py              # FastAPI application
├── config.py            # Configuration management
├── database.py          # Database connection and session management
├── exceptions.py        # Custom exceptions and handlers
├── models.py           # Pydantic models
├── routes/             # API routes
│   ├── v1_api.py       # V1 API endpoints
│   ├── v2_api.py       # V2 API endpoints
│   ├── auth.py         # Authentication endpoints
│   └── health.py       # Health check endpoints
├── auth/               # Authentication module
│   ├── models.py       # SQLAlchemy Core table definitions
│   ├── schemas.py      # Pydantic DTOs for auth
│   ├── auth_dep.py     # Auth dependencies and middleware
│   ├── token_service.py # JWT and refresh token services
│   └── google_auth.py  # Google ID token verification
└── services/           # Business logic services
    ├── image_service.py    # Image processing
    ├── text_service.py     # Text analysis
    ├── rate_limiter.py     # Rate limiting
    └── llm/               # LLM services
        └── open_ai.py      # OpenAI integration
```

## Testing Plan

### Unit Tests

1. **Token Verification**:
   - Test JWT access token generation and verification
   - Test refresh token hashing and verification
   - Test token expiration handling
   - Test invalid token rejection

2. **Refresh Token Rotation**:
   - Test old token revocation on refresh
   - Test new token generation and storage
   - Test token lookup by device_id

3. **Device Count Increment**:
   - Test atomic increment of device request count
   - Test blocking when limit exceeded
   - Test concurrent request handling

4. **Logout Revocation**:
   - Test token revocation for single device
   - Test token revocation for all devices

### Integration Tests

1. **Login Flow**:
   - Mock Google ID token verification
   - Test user creation/update
   - Test token generation and storage
   - Verify response format

2. **Refresh Flow**:
   - Test refresh token lookup
   - Test token rotation
   - Test new access token generation

3. **Protected Endpoints**:
   - Test access with valid token
   - Test rejection with invalid/expired token
   - Test device counting for unauthenticated requests

4. **Concurrent Device Counting**:
   - Test multiple simultaneous requests from same device
   - Verify atomic increment behavior
   - Test limit enforcement

### Example Test Structure

```python
# tests/test_auth.py
import pytest
from app.auth.token_service import generate_access_token, verify_access_token
from app.auth.auth_dep import get_current_user_or_device

@pytest.mark.asyncio
async def test_access_token_generation():
    token = generate_access_token(user_id=1, email="test@example.com", device_id="device-123")
    assert token is not None
    
    payload = verify_access_token(token)
    assert payload["sub"] == "1"
    assert payload["email"] == "test@example.com"

@pytest.mark.asyncio
async def test_device_count_increment(db_session):
    # Test device count increment logic
    pass

@pytest.mark.asyncio
async def test_refresh_token_rotation(db_session):
    # Test refresh token rotation on /auth/refresh
    pass
```

## Production Deployment

### Docker Production Setup

1. Build production image:
```bash
docker build -t caten-api .
```

2. Run with production settings:
```bash
docker run -d \
  --name caten-api \
  -p 8000:8000 \
  -e OPENAI_API_KEY=your_key \
  -e DEBUG=false \
  -e LOG_LEVEL=WARNING \
  caten-api
```

### Kubernetes Deployment

Example deployment configuration is available in the `k8s/` directory (if provided).

### Environment Considerations

- Set `DEBUG=false` in production
- Use `LOG_LEVEL=WARNING` or `ERROR` in production
- Configure proper rate limiting based on your needs
- Set up monitoring and alerting for the `/health` endpoint
- Use a proper Redis instance for rate limiting
- Configure CORS appropriately for your frontend domains

## Security

- **Authentication**: Google ID token-based authentication with JWT access tokens and refresh tokens
- **Token Security**: Refresh tokens are hashed before storage; access tokens are short-lived (15 min default)
- **Device Limits**: Unauthenticated requests are limited per device (20 requests default)
- **File Uploads**: Validated for type and size
- **Rate Limiting**: Prevents abuse with configurable limits
- **Input Validation**: All endpoints validate input using Pydantic
- **Error Handling**: Structured error responses don't leak sensitive information
- **TLS**: All production deployments should use HTTPS/TLS

## License

[Add your license information here]

## Contributing

[Add contribution guidelines here]
