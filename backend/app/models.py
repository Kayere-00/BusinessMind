"""ORM models. Every tenant-owned row carries org_id for strict isolation."""
import enum
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, enum.Enum):
    admin = "admin"
    analyst = "analyst"
    viewer = "viewer"


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(sa.String(120), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=_utcnow)

    users: Mapped[list["User"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    datasets: Mapped[list["Dataset"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    assistant_conversations: Mapped[list["AssistantConversation"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    business_context: Mapped["BusinessContext | None"] = relationship(
        back_populates="organization", cascade="all, delete-orphan", uselist=False
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(sa.ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(sa.String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(sa.String(120))
    password_hash: Mapped[str] = mapped_column(sa.String(255))
    role: Mapped[Role] = mapped_column(sa.Enum(Role), default=Role.viewer)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=_utcnow)

    organization: Mapped[Organization] = relationship(back_populates="users")
    assistant_conversations: Mapped[list["AssistantConversation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(sa.ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(sa.String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=_utcnow)


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(sa.ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(sa.String(200))
    original_filename: Mapped[str] = mapped_column(sa.String(255))
    stored_path: Mapped[str] = mapped_column(sa.String(500))
    row_count: Mapped[int] = mapped_column(sa.Integer)
    col_count: Mapped[int] = mapped_column(sa.Integer)
    profile: Mapped[dict] = mapped_column(sa.JSON, default=dict)
    uploaded_by: Mapped[str] = mapped_column(sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=_utcnow)

    organization: Mapped[Organization] = relationship(back_populates="datasets")
    assistant_conversations: Mapped[list["AssistantConversation"]] = relationship(
        back_populates="dataset"
    )


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(sa.ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    dataset_id: Mapped[str] = mapped_column(sa.ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(sa.String(200))
    stored_path: Mapped[str] = mapped_column(sa.String(500))
    created_by: Mapped[str] = mapped_column(sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=_utcnow)


class AssistantConversation(Base):
    __tablename__ = "assistant_conversations"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(sa.ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(sa.ForeignKey("users.id", ondelete="CASCADE"), index=True)
    dataset_id: Mapped[str | None] = mapped_column(
        sa.ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(sa.String(120), default="New conversation")
    summary: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    summarized_message_count: Mapped[int] = mapped_column(sa.Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    messages: Mapped[list["AssistantMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="AssistantMessage.created_at"
    )
    organization: Mapped[Organization] = relationship(back_populates="assistant_conversations")
    user: Mapped[User] = relationship(back_populates="assistant_conversations")
    dataset: Mapped[Dataset | None] = relationship(back_populates="assistant_conversations")


class AssistantMessage(Base):
    __tablename__ = "assistant_messages"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(sa.ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[str] = mapped_column(
        sa.ForeignKey("assistant_conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(sa.String(16))
    content: Mapped[str] = mapped_column(sa.Text)
    message_metadata: Mapped[dict] = mapped_column(sa.JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=_utcnow)

    conversation: Mapped[AssistantConversation] = relationship(back_populates="messages")


class BusinessContext(Base):
    __tablename__ = "business_context"

    org_id: Mapped[str] = mapped_column(
        sa.ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    context_text: Mapped[str] = mapped_column(sa.Text, default="")
    updated_by: Mapped[str | None] = mapped_column(
        sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    organization: Mapped[Organization] = relationship(back_populates="business_context")
