import re
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..core.config import settings
from ..core.deps import get_current_user
from ..core.security import (
    hash_password,
    verify_password,
    create_access_token,
    auth_rate_limiter,
    get_trusted_client_ip,
)
from ..db.session import get_db
from ..models.db import User, Organization, OrganizationMember
from ..models.auth_schemas import (
    UserSignup,
    UserLogin,
    AuthResponse,
    CurrentUserResponse,
    UserOut,
    OrgOut,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _get_client_ip(request: Request) -> str:
    return get_trusted_client_ip(request)


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


def _clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.COOKIE_NAME,
        path="/",
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
    )


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    payload: UserSignup,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    client_ip = _get_client_ip(request)
    if auth_rate_limiter.is_rate_limited(f"signup:{client_ip}", max_attempts=10, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many signup attempts. Please try again in a minute.",
        )

    email = payload.email.strip().lower()
    if not EMAIL_REGEX.match(email):
        raise HTTPException(
            status_code=422,
            detail="Invalid email address format.",
        )

    # Check if user already exists
    existing_user = db.scalar(select(User).where(User.email == email))
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists.",
        )

    # Hash password with Argon2
    hashed_pwd = hash_password(payload.password)

    # Create User
    user = User(
        email=email,
        hashed_password=hashed_pwd,
        full_name=payload.full_name.strip() if payload.full_name else None,
        is_active=True,
    )
    db.add(user)
    db.flush()

    # Create default Organization
    org_title = payload.org_name.strip() if payload.org_name else f"{(payload.full_name or email.split('@')[0])}'s Workspace"
    clean_slug = re.sub(r"[^a-z0-9]+", "-", org_title.lower()).strip("-") or "workspace"
    unique_slug = f"{clean_slug}-{user.id[:8]}"

    org = Organization(
        name=org_title,
        slug=unique_slug,
    )
    db.add(org)
    db.flush()

    # Assign user as Owner of their organization
    membership = OrganizationMember(
        organization_id=org.id,
        user_id=user.id,
        role="owner",
    )
    db.add(membership)
    db.commit()
    db.refresh(user)

    # Generate JWT
    token = create_access_token({"sub": user.id, "email": user.email})
    _set_auth_cookie(response, token)

    return AuthResponse(
        access_token=token,
        token_type="bearer",
        user=UserOut(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
        organizations=[
            OrgOut(
                id=org.id,
                name=org.name,
                slug=org.slug,
                role="owner",
            )
        ],
        active_organization_id=org.id,
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: UserLogin,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    client_ip = _get_client_ip(request)
    email = payload.email.strip().lower()

    # 1. IP-level rate limit: prevent distributed credential stuffing / spraying from single IP
    if auth_rate_limiter.is_rate_limited(f"login_ip:{client_ip}", max_attempts=30, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts from this address. Please wait 60 seconds before trying again.",
        )

    # 2. Account-level rate limit: prevent brute-forcing a specific user account
    if auth_rate_limiter.is_rate_limited(f"login:{client_ip}:{email}", max_attempts=5, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please wait 60 seconds before trying again.",
        )

    user = db.scalar(select(User).where(User.email == email))
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )

    # Reset rate limit counter on successful login
    auth_rate_limiter.reset(f"login:{client_ip}:{email}")

    # Fetch user's organizations
    memberships = db.scalars(
        select(OrganizationMember).where(OrganizationMember.user_id == user.id)
    ).all()

    orgs_out = [
        OrgOut(
            id=m.organization.id,
            name=m.organization.name,
            slug=m.organization.slug,
            role=m.role,
        )
        for m in memberships
        if m.organization
    ]

    active_org_id = orgs_out[0].id if orgs_out else ""

    token = create_access_token({"sub": user.id, "email": user.email})
    _set_auth_cookie(response, token)

    return AuthResponse(
        access_token=token,
        token_type="bearer",
        user=UserOut(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
        organizations=orgs_out,
        active_organization_id=active_org_id,
    )


@router.post("/logout")
async def logout(response: Response) -> dict:
    _clear_auth_cookie(response)
    return {"status": "ok", "message": "Logged out successfully."}


@router.get("/me", response_model=CurrentUserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CurrentUserResponse:
    memberships = db.scalars(
        select(OrganizationMember).where(OrganizationMember.user_id == current_user.id)
    ).all()

    orgs_out = [
        OrgOut(
            id=m.organization.id,
            name=m.organization.name,
            slug=m.organization.slug,
            role=m.role,
        )
        for m in memberships
        if m.organization
    ]

    active_org_id = orgs_out[0].id if orgs_out else None

    return CurrentUserResponse(
        user=UserOut(
            id=current_user.id,
            email=current_user.email,
            full_name=current_user.full_name,
            is_active=current_user.is_active,
            created_at=current_user.created_at,
        ),
        organizations=orgs_out,
        active_organization_id=active_org_id,
    )
