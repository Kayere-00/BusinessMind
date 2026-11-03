"""Auth routes: register organization, login, refresh rotation, logout, me."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Organization, RefreshToken, Role, User
from ..schemas import LoginRequest, RefreshRequest, RegisterRequest, TokenPair, UserOut
from ..security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

GENERIC_AUTH_ERROR = "Invalid email or password."


def _issue_tokens(db: Session, user: User) -> TokenPair:
    access = create_access_token(user.id, user.org_id, user.role.value)
    refresh = create_refresh_token(user.id, user.org_id, user.role.value)
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    ))
    db.commit()
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/register", response_model=TokenPair, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    email = payload.email.lower()
    if db.scalar(select(func.count(User.id)).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")
    org_name = payload.org_name.strip()
    # Organization names are unique tenants: you cannot self-join an existing
    # organization — members are added later by an admin through /api/users.
    if db.scalar(select(func.count(Organization.id)).where(Organization.name == org_name)):
        raise HTTPException(status.HTTP_409_CONFLICT, "This organization name is already taken.")
    org = Organization(name=org_name)
    db.add(org)
    db.flush()
    user = User(
        org_id=org.id, email=email, full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        role=Role.admin,  # the creator of an organization is its first admin
    )
    db.add(user)
    db.commit()
    return _issue_tokens(db, user)


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, GENERIC_AUTH_ERROR)
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been deactivated.")
    return _issue_tokens(db, user)


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    claims = decode_token(payload.refresh_token, expected_type="refresh")
    if claims is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token.")
    token_hash = hash_refresh_token(payload.refresh_token)
    stored = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if stored is None or stored.revoked or _as_utc(stored.expires_at) < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token expired or revoked.")
    user = db.get(User, stored.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account unavailable.")
    stored.revoked = True  # rotation: old token is single-use
    return _issue_tokens(db, user)


@router.post("/logout", status_code=204)
def logout(payload: RefreshRequest, db: Session = Depends(get_db)):
    stored = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(payload.refresh_token))
    )
    if stored:
        stored.revoked = True
        db.commit()


@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)):
    return UserOut(
        id=current.id, email=current.email, full_name=current.full_name,
        role=current.role.value, is_active=current.is_active,
        org_id=current.org_id, org_name=current.organization.name if current.organization else None,
        created_at=current.created_at,
    )
