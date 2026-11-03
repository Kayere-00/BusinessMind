"""Pydantic request/response schemas — strict input validation lives here."""
import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

PASSWORD_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{10,128}$")


def _validate_password(v: str) -> str:
    if not PASSWORD_RE.match(v):
        raise ValueError(
            "Password must be 10-128 characters and contain uppercase, lowercase and a digit."
        )
    return v


class RegisterRequest(BaseModel):
    org_name: str = Field(min_length=2, max_length=120)
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str

    _pw = field_validator("password")(_validate_password)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=10, max_length=4096)


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    org_id: str
    org_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateUserRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str
    role: Literal["admin", "analyst", "viewer"] = "viewer"

    _pw = field_validator("password")(_validate_password)


class UpdateUserRequest(BaseModel):
    role: Literal["admin", "analyst", "viewer"] | None = None
    is_active: bool | None = None


class DatasetOut(BaseModel):
    id: str
    name: str
    original_filename: str
    row_count: int
    col_count: int
    created_at: datetime
    profile: dict[str, Any] | None = None

    model_config = {"from_attributes": True}


class AskRequest(BaseModel):
    dataset_id: str = Field(min_length=36, max_length=36)
    question: str = Field(min_length=3, max_length=1000)


class AskResponse(BaseModel):
    answer: str
    narrative: str | None = None
    narrative_source: Literal["ollama", "builtin", "none"] = "none"
    chart: dict[str, Any] | None = None
    table: dict[str, Any] | None = None
    computed: dict[str, Any] | None = None


class ConversationCreateRequest(BaseModel):
    dataset_id: str | None = Field(default=None, min_length=36, max_length=36)
    title: str | None = Field(default=None, min_length=1, max_length=120)


class ConversationOut(BaseModel):
    id: str
    dataset_id: str | None
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AssistantMessageOut(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetail(ConversationOut):
    summary: str | None = None
    messages: list[AssistantMessageOut] = Field(default_factory=list)


class AssistantMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class BusinessContextUpdate(BaseModel):
    context_text: str = Field(max_length=5000)


class BusinessContextOut(BaseModel):
    context_text: str
    updated_at: datetime | None = None


class ReportCreateRequest(BaseModel):
    dataset_id: str = Field(min_length=36, max_length=36)
    title: str = Field(min_length=3, max_length=200)


class ReportOut(BaseModel):
    id: str
    dataset_id: str
    title: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ErrorOut(BaseModel):
    detail: str
