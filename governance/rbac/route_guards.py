"""SoD route guards + persona matrix (PLATFORM-33, blueprint Part 19.3/19.6, Part 27.2).

Enforces Separation of Duties in software: the four personas (builder / labeler / actor /
administrator) are DISJOINT — whoever **builds** models cannot **label** data, cannot **act**
on alerts, and cannot **administer** the platform (and vice-versa). This is the exact
anti-pattern the whole system is built to catch (Part 19.3), applied to the programme itself.

Keycloak seeds the realm roles (deploy/compose/config/keycloak/hawk-eye-realm.json); BACKEND
owns the API. This module provides the reusable enforcement primitive + the SoD matrix that
the demo (governance/rbac/demo.py) and route guards use.
"""
from __future__ import annotations

import os

import jwt  # PyJWT

JWT_SECRET = os.environ.get("SOD_JWT_SECRET", "dev-sod-secret")
PERSONAS = ("builder", "labeler", "actor", "administrator")

# Each duty is permitted to exactly ONE persona — the SoD matrix.
DUTY_PERSONA = {
    "build_model": "builder",
    "touch_training_data": "builder",   # the builder owns training data + model build
    "label_data": "labeler",            # labeling is segregated from building (poisoning defence)
    "act_on_alert": "actor",            # investigators act; cannot build or label
    "administer_platform": "administrator",
}

# Conflicting persona pairs that must never co-occur on one identity (toxic combinations).
TOXIC_PAIRS = [
    ("builder", "labeler"),     # who builds cannot label (Part 19.2 poisoning)
    ("builder", "actor"),       # who builds cannot close their own alerts (Part 19.3)
    ("actor", "administrator"), # who acts cannot administer
    ("labeler", "administrator"),
]


def make_token(username: str, personas: list[str]) -> str:
    return jwt.encode({"sub": username, "personas": personas}, JWT_SECRET, algorithm="HS256")


def decode(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])


def personas_of(token: str) -> list[str]:
    return decode(token).get("personas", [])


class SoDViolation(Exception):
    pass


def assert_no_toxic_combo(personas: list[str]) -> None:
    """Reject an identity that holds a toxic persona combination (Part 19.3 SoD)."""
    pset = set(personas)
    for a, b in TOXIC_PAIRS:
        if a in pset and b in pset:
            raise SoDViolation(f"toxic SoD combination: {a} + {b} on one identity")


def can(personas: list[str], duty: str) -> bool:
    """Does any of the identity's personas permit this duty?"""
    required = DUTY_PERSONA.get(duty)
    return required is not None and required in personas


def enforce(token: str, duty: str) -> None:
    """Route-guard primitive: raise SoDViolation unless the token's persona permits the duty."""
    personas = personas_of(token)
    assert_no_toxic_combo(personas)
    if not can(personas, duty):
        required = DUTY_PERSONA.get(duty, "<unknown>")
        raise SoDViolation(f"persona(s) {personas} cannot perform '{duty}' (requires '{required}')")


# --- FastAPI dependency factory (used by services that gate routes) ----------
def require_duty(duty: str):
    """Returns a FastAPI dependency that enforces `duty` from a Bearer token."""
    from fastapi import Header, HTTPException

    def _dep(authorization: str = Header(default="")) -> dict:
        token = authorization.removeprefix("Bearer ").strip()
        try:
            claims = decode(token)
            enforce(token, duty)
        except SoDViolation as e:
            raise HTTPException(403, str(e))
        except Exception:
            raise HTTPException(401, "invalid token")
        return claims

    return _dep
