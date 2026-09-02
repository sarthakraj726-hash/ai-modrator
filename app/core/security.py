"""Security utilities, API key authentication, and administrative boundaries."""

import secrets

from fastapi import Header, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.rbac import Role, UserContext

security_bearer = HTTPBearer(auto_error=False)


def verify_admin_secret(
    x_admin_secret: str | None = Header(None, alias="X-Admin-Secret"),
    credentials: HTTPAuthorizationCredentials | None = Security(security_bearer),
) -> UserContext:
    """
    Validate admin secret from X-Admin-Secret header or Bearer token.
    Grants DEVELOPER role on match.
    """
    settings = get_settings()
    expected_secret = settings.ADMIN_SECRET

    provided_secret: str | None = None
    if x_admin_secret:
        provided_secret = x_admin_secret
    elif credentials and credentials.credentials:
        provided_secret = credentials.credentials

    if not provided_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing admin credentials (provide X-Admin-Secret header or Bearer token)",
        )

    # Constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(provided_secret, expected_secret):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin credentials",
        )

    return UserContext(user_id="admin-developer", role=Role.DEVELOPER)


def generate_secure_token(n_bytes: int = 32) -> str:
    """Generate a cryptographically secure random hexadecimal token."""
    return secrets.token_hex(n_bytes)
