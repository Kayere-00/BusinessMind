"""User management (admin only) — scoped strictly to the caller's organization."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import admin_only
from ..models import Role, User
from ..schemas import CreateUserRequest, UpdateUserRequest, UserOut
from ..security import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


def _out(u: User) -> UserOut:
    return UserOut(
        id=u.id, email=u.email, full_name=u.full_name, role=u.role.value,
        is_active=u.is_active, org_id=u.org_id,
        org_name=u.organization.name if u.organization else None, created_at=u.created_at,
    )


@router.get("", response_model=list[UserOut])
def list_users(current: User = Depends(admin_only), db: Session = Depends(get_db)):
    users = db.scalars(select(User).where(User.org_id == current.org_id).order_by(User.created_at)).all()
    return [_out(u) for u in users]


@router.post("", response_model=UserOut, status_code=201)
def create_user(payload: CreateUserRequest, current: User = Depends(admin_only), db: Session = Depends(get_db)):
    email = payload.email.lower()
    if db.scalar(select(func.count(User.id)).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")
    user = User(
        org_id=current.org_id, email=email, full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password), role=Role(payload.role),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _out(user)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: str, payload: UpdateUserRequest, current: User = Depends(admin_only), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.id == user_id, User.org_id == current.org_id))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    if user.id == current.id and payload.is_active is False:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot deactivate your own account.")
    if payload.role is not None:
        user.role = Role(payload.role)
    if payload.is_active is not None:
        user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    return _out(user)


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: str, current: User = Depends(admin_only), db: Session = Depends(get_db)):
    if user_id == current.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot delete your own account.")
    user = db.scalar(select(User).where(User.id == user_id, User.org_id == current.org_id))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    db.delete(user)
    db.commit()
