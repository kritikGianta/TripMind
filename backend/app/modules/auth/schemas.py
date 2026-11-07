"""Auth API contract. These models generate the OpenAPI schema the frontend types come from."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

Password = Annotated[str, Field(min_length=8, max_length=128)]
FullName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: Password
    full_name: FullName


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: Annotated[str, Field(min_length=1, max_length=128)]


class DemoLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["traveler", "admin"] = "traveler"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: Literal["traveler", "admin"]
    created_at: datetime


class SessionOut(BaseModel):
    """Returned after sign-in, sign-up and refresh. Tokens travel only in httpOnly cookies."""

    user: UserOut
    access_expires_at: datetime
