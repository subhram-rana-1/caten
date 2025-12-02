# Chrome Extension OAuth Integration Prompt

## Overview
Add Google OAuth2 authentication functionality to an **existing Chrome extension**. **Detect the technology stack** used in the extension and implement OAuth using the best practices and patterns for that stack. Implement automatic token management, device ID tracking, and seamless authentication flow that integrates seamlessly with the existing extension codebase.

## Context
- The Chrome extension **already exists**
- You need to **add OAuth functionality** to the existing codebase
- **Do not rebuild the extension** - only add OAuth features

## Approach
1. **Detect existing technology stack** - Examine the codebase to identify:
   - Framework/library being used (if any)
   - Programming language (JavaScript, TypeScript, etc.)
   - UI framework (React, Vue, vanilla JS, etc.)
   - Build system and project structure
   - Existing patterns and conventions

2. **Implement OAuth using detected stack** - Use the best practices and patterns for the detected technology:
   - Follow existing code style and conventions
   - Use appropriate patterns for the detected framework
   - Integrate with existing architecture seamlessly

3. **Examine existing codebase** - Understand current structure, API patterns, and UI components

4. **Add OAuth modules** - Create new utility files for authentication following existing patterns

5. **Enhance existing code** - Update existing API utilities to include token handling

6. **Update UI** - Modify popup/UI to show auth states (logged in/out) using existing UI patterns

7. **Integrate seamlessly** - Ensure OAuth doesn't break existing functionality

## Core Requirements

### 1. Authentication UI Components

#### Update Popup HTML Component
Modify the existing popup to display different states based on authentication:

**When User is NOT Logged In:**
- Display a "Sign in with Google" button/option in the popup
- Button should trigger Google OAuth2 flow
- Use Google's official sign-in styling/iconography
- Integrate with existing popup layout and styling

**When User IS Logged In:**
- Display user's profile picture (circular image) in the popup
- Show greeting: "Hi {Name} 👋" (with greeting icon/emoji)
- Display a power off/logout button to sign out
- Profile picture should be clickable or have hover effects
- Replace or update existing popup content to show authenticated state

### 2. Device ID Management
- **Generate and persist a unique device ID** (UUID format) using `chrome.storage.local`
- Device ID must be **sent with every API request** in the `X-DEVICE-ID` header
- Device ID should be generated once per installation and reused across sessions
- Use format: UUID v4 (e.g., `550e8400-e29b-41d4-a716-446655440000`)

### 3. Token Management & Storage
- Store tokens securely using `chrome.storage.local`:
  - `access_token`: JWT access token
  - `refresh_token`: Opaque refresh token
  - `user`: User profile data (id, email, name, picture_url)
- Tokens should be cached and retrieved on extension startup
- Clear tokens on logout

### 4. API Request Interceptor
Create or update the existing API request function/wrapper to:
- **Always includes `X-DEVICE-ID` header** in every request
- **Automatically includes `Authorization: Bearer <access_token>` header** if token is cached
- Handles token refresh and retry logic transparently
- Returns response data or throws errors appropriately
- **Integrate with existing API request patterns** - if there's already an API utility, enhance it rather than replacing it

### 5. Automatic Token Refresh & Retry Logic

#### Scenario 1: 401 with "INVALID_ACCESS_TOKEN" or "TOKEN_NOT_PROVIDED"
- If API returns 401 with error_code `INVALID_ACCESS_TOKEN` or token is missing:
  - Show a **centered dialog box** asking user to sign in with Google
  - Dialog should have a Google sign-in button/icon
  - After successful Google sign-in:
    - Exchange Google ID token for backend tokens
    - Retry the original API call automatically
    - User should not see the 401 error - everything happens seamlessly

#### Scenario 2: 401 with "ACCESS_TOKEN_EXPIRED"
- If API returns 401 with error_code `ACCESS_TOKEN_EXPIRED`:
  - Automatically call `/auth/refresh` endpoint with refresh_token
  - If refresh succeeds:
    - Update stored access_token and refresh_token
    - Retry the original API call automatically
  - If refresh fails:
    - Show sign-in dialog (same as Scenario 1)
    - After sign-in, retry original API call
- User should not experience any interruption - all happens under the hood

#### Implementation Notes:
- All token refresh and retry logic must be **transparent to the user**
- Original API call should appear to succeed normally after token refresh
- No error messages should be shown to user during automatic token refresh
- Only show sign-in dialog when Google authentication is actually required

### 6. Google OAuth2 Integration

#### Configuration
- Make Google Client ID configurable (store in `chrome.storage.local` or manifest config)
- Use Google Identity Services (GIS) library for OAuth2
- Required scopes: `openid email profile`

#### Sign-In Flow
1. User clicks "Sign in with Google" button
2. Trigger Google OAuth2 popup/flow
3. Obtain Google ID token
4. Call `/auth/google` endpoint with:
   - `id_token`: Google ID token
   - `device_id`: Stored device ID
   - `device_info`: "Chrome Extension" (optional)
5. Store returned tokens and user data
6. Update UI to show logged-in state

#### Sign-Out Flow
1. User clicks logout/power off button
2. Call `/auth/logout` endpoint with access token
3. Clear all stored tokens and user data
4. Update UI to show logged-out state

### 7. Dialog Box for Sign-In
- Create a centered modal/dialog overlay
- Display when authentication is required (401 errors)
- Include:
  - Message: "Please sign in with Google to continue"
  - Google sign-in button/icon
  - Close button (optional, but should not allow bypassing auth)
- Dialog should be styled consistently with extension theme
- Should block interaction with extension until authenticated

## API Contracts

### Base URL Configuration
- Make API base URL configurable (e.g., `https://api.example.com` or `http://localhost:8000`)
- Store in `chrome.storage.local` or manifest config

### Authentication API Endpoints

#### POST /auth/google
**Purpose**: Exchange Google ID token for backend session tokens

**Request Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "id_token": "<Google ID token JWT string>",
  "device_id": "<UUID string>",
  "device_info": "Chrome Extension" // optional
}
```

**Success Response (200 OK):**
```json
{
  "access_token": "<JWT access token>",
  "token_type": "bearer",
  "expires_in": 900,
  "refresh_token": "<opaque refresh token>",
  "user": {
    "id": 123,
    "email": "user@example.com",
    "name": "User Name",
    "picture_url": "https://lh3.googleusercontent.com/..."
  }
}
```

**Error Responses:**
- `400 BAD_REQUEST`:
```json
{
  "detail": {
    "error_code": "BAD_REQUEST",
    "error_reason": "Missing id_token or device_id"
  }
}
```

- `401 UNAUTHORIZED`:
```json
{
  "detail": {
    "error_code": "INVALID_GOOGLE_TOKEN",
    "error_reason": "Google token invalid or expired"
  }
}
```

---

#### POST /auth/refresh
**Purpose**: Exchange refresh token for new access token (with token rotation)

**Request Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "refresh_token": "<opaque refresh token>",
  "device_id": "<UUID string>"
}
```

**Success Response (200 OK):**
```json
{
  "access_token": "<new JWT access token>",
  "token_type": "bearer",
  "expires_in": 900,
  "refresh_token": "<new opaque refresh token>"
}
```

**Error Responses:**
- `400 BAD_REQUEST`:
```json
{
  "detail": {
    "error_code": "BAD_REQUEST",
    "error_reason": "Missing refresh_token or device_id"
  }
}
```

- `401 UNAUTHORIZED`:
```json
{
  "detail": {
    "error_code": "INVALID_REFRESH_TOKEN",
    "error_reason": "Refresh token invalid or revoked"
  }
}
```

---

#### POST /auth/logout
**Purpose**: Revoke refresh tokens for authenticated user

**Request Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
X-DEVICE-ID: <UUID string>
```

**Request Body:**
```json
{
  "revoke_all": false
}
```

**Success Response (200 OK):**
```json
{
  "ok": true
}
```

**Error Responses:**
- `401 UNAUTHORIZED`:
```json
{
  "detail": {
    "error_code": "INVALID_ACCESS_TOKEN",
    "error_reason": "Authorization header missing or invalid"
  }
}
```

---

#### GET /auth/profile
**Purpose**: Get current authenticated user's profile

**Request Headers:**
```
Authorization: Bearer <access_token>
X-DEVICE-ID: <UUID string>
```

**Success Response (200 OK):**
```json
{
  "id": 123,
  "email": "user@example.com",
  "name": "User Name",
  "picture_url": "https://lh3.googleusercontent.com/...",
  "created_at": "2024-01-01T00:00:00Z",
  "last_login_at": "2024-01-01T00:00:00Z",
  "is_active": true
}
```

**Error Responses:**
- `401 UNAUTHORIZED`:
```json
{
  "detail": {
    "error_code": "INVALID_ACCESS_TOKEN",
    "error_reason": "Authorization header missing or invalid"
  }
}
```

or

```json
{
  "detail": {
    "error_code": "ACCESS_TOKEN_EXPIRED",
    "error_reason": "Access token expired; please refresh"
  }
}
```

---

## Error Code Handling

The backend returns error responses in this format:
```json
{
  "detail": {
    "error_code": "<ERROR_CODE>",
    "error_reason": "<Human readable reason>"
  }
}
```

**Key Error Codes:**
- `BAD_REQUEST`: Missing required fields
- `INVALID_GOOGLE_TOKEN`: Google ID token is invalid or expired
- `INVALID_ACCESS_TOKEN`: Access token is missing, invalid, or malformed
- `ACCESS_TOKEN_EXPIRED`: Access token has expired (trigger refresh)
- `INVALID_REFRESH_TOKEN`: Refresh token is invalid, expired, or revoked
- `TOKEN_NOT_PROVIDED_LIMIT_EXCEEDED`: Unauthenticated device exceeded request limit

## Implementation Guidelines

### 1. Files to Create/Modify
**Detect the existing project structure first**, then add or update files accordingly:

**New Files to Create (adapt paths to your detected structure):**
- Authentication utilities file (e.g., `utils/auth.js`, `lib/auth.ts`, `services/auth.js`, etc.) - Google OAuth, token management
- Device ID management file (if not exists) - Device ID generation and persistence
- Storage utilities file (if not exists, or enhance existing) - Chrome storage wrapper

**Files to Modify (adapt to detected structure):**
- Popup/UI HTML file - Add authentication UI elements
- Popup/UI script file - Add authentication state management
- Styles file - Add styles for auth UI components
- Existing API utility file - Enhance with token handling and device ID
- Manifest/config file - Add Google Identity Services script permission if needed

**Note:** 
- **Detect the existing project structure** and file organization patterns
- Work with the existing project structure - follow existing naming conventions and folder organization
- If files already exist, enhance them rather than creating duplicates
- Use appropriate file extensions based on detected language (`.js`, `.ts`, `.jsx`, `.tsx`, etc.)

### 2. Google OAuth2 Implementation
- Use Google Identity Services (GIS) library
- Load from: `https://accounts.google.com/gsi/client` (add to appropriate HTML file or manifest based on detected structure)
- Initialize with configurable client ID (read from storage or config)
- Use `google.accounts.oauth2.initTokenClient()` for OAuth2 token flow
- Alternative: Use `google.accounts.id.initialize()` with `google.accounts.id.prompt()` for One Tap
- Handle OAuth2 callback to obtain ID token
- Ensure GIS script is loaded before initializing (use `onload` callback or dynamic script loading)
- **Adapt implementation approach** based on detected framework (e.g., React hooks, Vue composables, vanilla JS modules, etc.)

### 3. Storage Keys
Use consistent storage keys:
- `device_id`: Device UUID
- `access_token`: JWT access token
- `refresh_token`: Opaque refresh token
- `user`: User profile object
- `api_base_url`: API base URL
- `google_client_id`: Google OAuth2 Client ID

### 4. API Request Function Signature
Create or enhance existing API request function (adapt syntax to detected language):

**JavaScript/TypeScript example:**
```javascript
async function apiRequest(endpoint, options = {}) {
  // options.method, options.body, options.headers, etc.
  // Automatically adds:
  // - X-DEVICE-ID header (always)
  // - Authorization header if token exists
  // - Handles token refresh and retry transparently
  // - Shows sign-in dialog if needed
  // Returns: Response data or throws error
}
```

**Integration Notes:**
- **Detect existing API patterns** (fetch wrapper, axios, custom utility, etc.)
- If an API utility already exists, wrap it or enhance it following existing patterns
- Use appropriate patterns for detected framework (e.g., React context, Vue composables, service classes, etc.)
- Ensure all existing API calls automatically benefit from token handling
- Maintain backward compatibility with existing API call patterns
- Follow existing error handling patterns

### 5. Token Refresh Flow
```javascript
async function refreshAccessToken() {
  // 1. Get refresh_token from storage
  // 2. Call /auth/refresh
  // 3. Update stored tokens
  // 4. Return new access_token
  // 5. If fails, trigger Google sign-in
}
```

### 6. Error Handling
- Parse error responses to extract `error_code` and `error_reason`
- Handle 401 errors based on `error_code`:
  - `ACCESS_TOKEN_EXPIRED` → Refresh token
  - `INVALID_ACCESS_TOKEN` or missing token → Show sign-in dialog
- All other errors should be handled normally (show to user if appropriate)

### 7. UI State Management
- **Detect existing state management approach** (React state, Vue reactivity, Redux, Zustand, vanilla JS, etc.)
- Track authentication state (logged in / logged out) using detected patterns
- Update UI reactively when state changes (using detected framework's reactivity system)
- Integrate with existing UI state management if present
- Show loading states during API calls (using existing loading/UI patterns)
- Handle errors gracefully with user-friendly messages (following existing error handling patterns)
- On extension startup/popup open, check authentication state and update UI accordingly

### 8. Configuration
Make the following configurable:
- **API Base URL**: Default to `http://localhost:8000` for development
- **Google Client ID**: Required, should be set during extension setup
- Store configuration in `chrome.storage.local` or `manifest.config.ts`

### 9. Security Considerations
- Never log tokens to console in production
- Use `chrome.storage.local` (not `sync`) for sensitive data
- Validate API responses before using data
- Handle network errors gracefully

### 10. User Experience
- Show loading indicators during authentication
- Provide clear feedback on errors (when not auto-handled)
- Ensure smooth transitions between logged-in/logged-out states
- Make sign-in dialog non-intrusive but clear
- Profile picture should have fallback (initials or default avatar)

## Testing Checklist
- [ ] Device ID is generated and persisted correctly
- [ ] Google sign-in flow works end-to-end
- [ ] Tokens are stored and retrieved correctly
- [ ] API requests include device ID and auth headers
- [ ] Token refresh happens automatically on expiry
- [ ] Sign-in dialog appears on 401 errors
- [ ] Original API calls retry after token refresh/sign-in
- [ ] Logout clears tokens and updates UI
- [ ] Profile picture and greeting display correctly
- [ ] Extension works after browser restart (tokens persist)
- [ ] Error handling works for all error codes
- [ ] Configuration (API URL, Client ID) is changeable
- [ ] **Existing extension features still work** after OAuth integration
- [ ] **No conflicts** with existing storage keys or API patterns
- [ ] **UI integration** looks seamless with existing popup design

## Integration Notes

### Working with Existing Codebase
- **Detect technology stack first** - Examine package.json, manifest, build config, and code structure
- **Preserve existing functionality** - OAuth should be additive, not breaking
- **Reuse existing patterns** - Follow the extension's existing code style, patterns, and conventions
- **Use appropriate patterns** - If React detected, use hooks/context; if Vue, use composables; if vanilla JS, use modules, etc.
- **Enhance, don't replace** - If API utilities exist, enhance them rather than creating new ones
- **Check existing storage** - Ensure OAuth storage keys don't conflict with existing keys
- **UI integration** - Add auth UI elements that fit with existing popup design and component patterns
- **Follow existing architecture** - Use same patterns for modules, imports, exports, etc.

### Manifest Updates
- **Detect manifest format** (manifest.json v2/v3, or framework-specific config)
- May need to add `identity` permission for Google OAuth
- May need to add `https://accounts.google.com/*` to `host_permissions` or `permissions`
- Ensure `chrome.storage.local` permission exists (usually already present)
- Update manifest using detected format and structure

### Script Loading
- **Detect how scripts are loaded** in the existing codebase (HTML script tags, dynamic imports, build system, etc.)
- Load Google Identity Services script using detected approach
- Ensure script loads before OAuth initialization
- Handle script loading errors gracefully
- Follow existing script loading patterns

## Additional Notes
- **Detect and adapt to existing patterns** - Use the same coding style, async patterns, error handling, etc.
- All API calls should handle CORS properly (backend already configured)
- Use appropriate async patterns for detected language/framework
- Implement proper error boundaries/handling following existing patterns
- Ensure extension works with detected manifest version (v2 or v3)
- Follow Chrome extension best practices for security and performance
- Consider implementing request queuing if multiple API calls happen simultaneously during token refresh
- Test that existing features still work after adding OAuth
- Ensure OAuth doesn't interfere with existing extension functionality
- **Choose the best implementation approach** based on detected technology stack

