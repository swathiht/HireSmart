"""Registration, login and role checks (PBKDF2 password hashing, HMAC-signed tokens)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time

from ..db.database import connect

ROLES = ("student", "recruiter")
_ITERATIONS = 200_000
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthError(ValueError):
    """Raised for invalid registration / login / token problems."""


def _hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS).hex()


def register(email: str, name: str, password: str, role: str) -> dict:
    email = email.strip().lower()
    if role not in ROLES:
        raise AuthError("Role must be 'student' or 'recruiter'.")
    if not _EMAIL_RE.match(email):
        raise AuthError("Please enter a valid email address.")
    if len(password) < 8:
        raise AuthError("Password must be at least 8 characters.")
    if not name.strip():
        raise AuthError("Name is required.")
    salt = secrets.token_bytes(16)
    try:
        with connect() as conn:
            cur = conn.execute(
                "INSERT INTO users (email, name, password_hash, salt, role) VALUES (?,?,?,?,?)",
                (email, name.strip(), _hash(password, salt), salt.hex(), role),
            )
            uid = cur.lastrowid
    except sqlite3.IntegrityError as exc:
        raise AuthError("An account with this email already exists.") from exc
    return {"id": uid, "email": email, "name": name.strip(), "role": role}


def login(email: str, password: str) -> dict:
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone()
    # compare against a dummy hash when the user does not exist to keep timing similar
    salt = bytes.fromhex(row["salt"]) if row else b"\x00" * 16
    candidate = _hash(password, salt)
    if not row or not hmac.compare_digest(candidate, row["password_hash"]):
        raise AuthError("Incorrect email or password.")
    return {"id": row["id"], "email": row["email"], "name": row["name"], "role": row["role"]}


def require_role(user: dict | None, role: str) -> dict:
    if not user:
        raise AuthError("Please log in first.")
    if user["role"] != role:
        raise AuthError(f"This page is only for {role}s.")
    return user


# --------------------------------------------------------------------------- tokens (for the FastAPI layer)
def _secret() -> bytes:
    return os.getenv("HIRESMART_SECRET", "dev-secret-change-me").encode()


def create_token(user: dict, ttl_seconds: int = 8 * 3600) -> str:
    payload = json.dumps({"uid": user["id"], "role": user["role"], "exp": int(time.time()) + ttl_seconds}).encode()
    body = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    sig = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def verify_token(token: str) -> dict:
    try:
        body, sig = token.split(".", 1)
        expected = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise AuthError("Invalid token.")
        padded = body + "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
    except (ValueError, json.JSONDecodeError) as exc:
        raise AuthError("Invalid token.") from exc
    if payload["exp"] < time.time():
        raise AuthError("Token expired.")
    return payload
