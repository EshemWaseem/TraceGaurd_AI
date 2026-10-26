from typing import Optional, List
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..db.session import get_db
from ..models.db import User, OrganizationMember
from .config import settings
from .security import decode_access_token


def get_token_from_request(request: Request) -> Optional[str]:
    """Extract JWT token from Authorization header or HttpOnly cookie."""
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    # Check cookie fallback
    cookie_token = request.cookies.get(settings.COOKIE_NAME)
    if cookie_token:
        return cookie_token
    return None


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Dependency that authenticates the current user. Raises 401 on missing or invalid token."""
    token = get_token_from_request(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Missing token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or session revoked.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    return user


def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Optional authentication for endpoints that support both authenticated and guest usage."""
    token = get_token_from_request(request)
    if not token:
        return None

    payload = decode_access_token(token)
    if not payload:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    user = db.scalar(select(User).where(User.id == user_id))
    if user and user.is_active:
        return user
    return None


def verify_organization_access(
    organization_id: str,
    user: User,
    db: Session,
    required_roles: Optional[List[str]] = None,
) -> OrganizationMember:
    """
    Verify that the user is an authorized member of the organization.
    Prevents Insecure Direct Object References (IDOR).
    Raises 404 or 403 if unauthorized.
    """
    membership = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user.id,
        )
    )

    if not membership:
        # Return 404 to avoid leaking existence of foreign organizations
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found or access denied.",
        )

    if required_roles and membership.role not in required_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions. Required role: {', '.join(required_roles)}.",
        )

    return membership
