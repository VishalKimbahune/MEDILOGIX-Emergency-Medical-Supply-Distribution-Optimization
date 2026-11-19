"""
Centralized FastAPI Authentication & Role-Based Access Control (RBAC) Dependencies.

Every protected endpoint MUST depend on `get_current_user` or `require_roles(...)`.
Never trust frontend-supplied user IDs or roles; identity is extracted exclusively
from a verified signed JWT access token and re-checked against the live `users` table.
"""

from __future__ import annotations

from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database.connection import get_db
from app.models.user import User

_bearer_scheme = HTTPBearer(auto_error=False)


def get_client_ip(request: Request) -> str | None:
    """Extract client IP address safely for rate limiting and audit logging."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Validate Bearer JWT, load the User from DB, and verify account is active & approved.

    Raises HTTP 401 on missing/invalid/expired tokens, HTTP 403 on inactive/unapproved accounts.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide a valid Bearer access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user account no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive. Contact an administrator.",
        )

    if not user.is_approved or user.approval_status != "approved":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account approval status is '{user.approval_status}'. Administrator approval is required.",
        )

    return user


def require_roles(*allowed_roles: str) -> Callable[..., User]:
    """Dependency factory enforcing that the authenticated user holds one of `allowed_roles`."""
    allowed = {r.lower() for r in allowed_roles}

    def _checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role.lower() not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Access denied. Role '{current_user.role}' is not authorized for this resource."
                ),
            )
        return current_user

    return _checker


require_admin = require_roles("admin")
require_hospital_user = require_roles("hospital")
require_warehouse_user = require_roles("warehouse")
require_delivery_user = require_roles("delivery")
