"""Keycloak OIDC auth + short-lived JWT issue/refresh/validate (BACKEND-2, blueprint Part 24.1/24.2).

Two modes (``HAWKEYE_AUTH_MODE``):
* ``local``   — the API issues and validates its own short-lived HS256 tokens against a synthetic
                user directory. No external dependency; used for local dev + tests.
* ``keycloak``— ``login`` performs an OIDC token exchange against the Keycloak realm token
                endpoint; access tokens are validated as RS256 against the realm JWKS.

Tokens are deliberately short-lived (default 15 min access / 12 h refresh). Refresh ROTATES the
refresh token. The decoded claims become an ``app.auth.principal.Principal``.
"""

from __future__ import annotations

import time
import uuid

import requests
from authlib.jose import JsonWebKey, jwt
from authlib.jose.errors import JoseError

from app.auth.principal import Principal
from app.config import settings
from app.schemas.common import Role
from app.store.user_store import USER_STORE, User


class TokenError(Exception):
    """Raised for any invalid/expired/missing token."""


# --- Local HS256 issuance ------------------------------------------------------------------
def _claims(user: User, typ: str, ttl: int) -> dict:
    now = int(time.time())
    return {
        "iss": settings.jwt_issuer,
        "sub": user.user_id,
        "name": user.display_name,
        "role": user.role.value,
        "assigned_alerts": sorted(user.assigned_alerts),
        "de_identified_only": user.de_identified_only,
        "scopes": user.scopes,
        "typ": typ,
        "iat": now,
        "exp": now + ttl,
        "jti": uuid.uuid4().hex,
    }


def _encode(claims: dict) -> str:
    token = jwt.encode({"alg": "HS256", "typ": "JWT"}, claims, settings.dev_jwt_secret)
    return token.decode("utf-8") if isinstance(token, bytes) else token


def issue_tokens(user: User) -> dict:
    """Issue an access + refresh token pair for a (already authenticated) user."""
    access = _encode(_claims(user, "access", settings.access_token_ttl_seconds))
    refresh = _encode(_claims(user, "refresh", settings.refresh_token_ttl_seconds))
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "Bearer",
        "expires_in": settings.access_token_ttl_seconds,
        "role": user.role.value,
        "sub": user.user_id,
    }


def login(user_id: str, password: str) -> dict:
    """Authenticate and issue tokens (local mode) or exchange via Keycloak (keycloak mode)."""
    if settings.auth_mode == "keycloak":
        return _login_keycloak(user_id, password)
    user = USER_STORE.authenticate(user_id, password)
    if not user:
        raise TokenError("invalid credentials")
    return issue_tokens(user)


def refresh(refresh_token: str) -> dict:
    """Validate a refresh token and rotate it (issue a fresh access + refresh pair)."""
    if settings.auth_mode == "keycloak":
        return _refresh_keycloak(refresh_token)
    claims = _decode_local(refresh_token)
    if claims.get("typ") != "refresh":
        raise TokenError("not a refresh token")
    user = USER_STORE.get(claims["sub"])
    if not user:
        raise TokenError("unknown subject")
    return issue_tokens(user)  # rotation: a brand-new refresh token is returned


def validate_access_token(token: str) -> Principal:
    """Validate an access token and return the Principal (the JWT-validation middleware uses this)."""
    if settings.auth_mode == "keycloak":
        claims = _decode_keycloak(token)
    else:
        claims = _decode_local(token)
        if claims.get("typ") != "access":
            raise TokenError("not an access token")
    return _principal_from_claims(claims)


def _decode_local(token: str) -> dict:
    try:
        claims = jwt.decode(token, settings.dev_jwt_secret)
        claims.validate(now=int(time.time()), leeway=5)
    except JoseError as exc:  # expired / bad signature / malformed
        raise TokenError(f"invalid token: {exc}") from exc
    return dict(claims)


def _principal_from_claims(claims: dict) -> Principal:
    try:
        role = Role(claims.get("role"))
    except ValueError as exc:
        raise TokenError(f"unknown role: {claims.get('role')}") from exc
    return Principal(
        user_id=claims["sub"],
        role=role,
        display_name=claims.get("name", ""),
        assigned_alerts=set(claims.get("assigned_alerts", []) or []),
        de_identified_only=bool(claims.get("de_identified_only", False)),
        scopes=list(claims.get("scopes", []) or []),
        token_id=claims.get("jti", ""),
    )


# --- Keycloak OIDC (RS256 / JWKS) ----------------------------------------------------------
def _kc_token_endpoint() -> str:
    base = settings.keycloak_base_url.rstrip("/")
    return f"{base}/realms/{settings.keycloak_realm}/protocol/openid-connect/token"


def _kc_certs_endpoint() -> str:
    base = settings.keycloak_base_url.rstrip("/")
    return f"{base}/realms/{settings.keycloak_realm}/protocol/openid-connect/certs"


def _login_keycloak(username: str, password: str) -> dict:  # pragma: no cover - needs Keycloak
    data = {
        "grant_type": "password",
        "client_id": settings.keycloak_client_id,
        "client_secret": settings.keycloak_client_secret,
        "username": username,
        "password": password,
        "scope": "openid",
    }
    resp = requests.post(_kc_token_endpoint(), data=data, timeout=10)
    if resp.status_code != 200:
        raise TokenError(f"keycloak login failed: {resp.status_code}")
    body = resp.json()
    return {
        "access_token": body["access_token"],
        "refresh_token": body.get("refresh_token", ""),
        "token_type": "Bearer",
        "expires_in": body.get("expires_in", settings.access_token_ttl_seconds),
    }


def _refresh_keycloak(refresh_token: str) -> dict:  # pragma: no cover - needs Keycloak
    data = {
        "grant_type": "refresh_token",
        "client_id": settings.keycloak_client_id,
        "client_secret": settings.keycloak_client_secret,
        "refresh_token": refresh_token,
    }
    resp = requests.post(_kc_token_endpoint(), data=data, timeout=10)
    if resp.status_code != 200:
        raise TokenError("keycloak refresh failed")
    body = resp.json()
    return {
        "access_token": body["access_token"],
        "refresh_token": body.get("refresh_token", refresh_token),
        "token_type": "Bearer",
        "expires_in": body.get("expires_in", settings.access_token_ttl_seconds),
    }


_jwks_cache: dict[str, object] = {}


def _decode_keycloak(token: str) -> dict:  # pragma: no cover - needs Keycloak
    jwks = _jwks_cache.get("jwks")
    if jwks is None:
        resp = requests.get(_kc_certs_endpoint(), timeout=10)
        jwks = JsonWebKey.import_key_set(resp.json())
        _jwks_cache["jwks"] = jwks
    try:
        claims = jwt.decode(token, jwks)
        claims.validate(now=int(time.time()), leeway=5)
    except JoseError as exc:
        raise TokenError(f"invalid keycloak token: {exc}") from exc
    claims = dict(claims)
    # Map Keycloak realm roles → our Role enum (realm_access.roles[0] convention).
    realm_roles = (claims.get("realm_access") or {}).get("roles", [])
    for r in realm_roles:
        try:
            claims["role"] = Role(r).value
            break
        except ValueError:
            continue
    claims.setdefault("name", claims.get("preferred_username", ""))
    return claims
