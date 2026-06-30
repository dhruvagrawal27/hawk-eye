"""Auth routes (BACKEND-2): OIDC token exchange + refresh (public)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.oidc import TokenError, login, refresh

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(..., examples=["EMP-an01"])
    password: str = Field(..., examples=["hawk-eye"])


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    role: str | None = None
    sub: str | None = None


@router.post("/auth/login", response_model=TokenResponse)
def auth_login(body: LoginRequest) -> TokenResponse:
    try:
        return TokenResponse(**login(body.username, body.password))
    except TokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/auth/refresh", response_model=TokenResponse)
def auth_refresh(body: RefreshRequest) -> TokenResponse:
    try:
        return TokenResponse(**refresh(body.refresh_token))
    except TokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
