"""
Authentication service.
Handles user registration, login, and JWT token management.
"""

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from pydantic import BaseModel

from .leads import DB_PATH


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())

# ── JWT config ────────────────────────────────────────────────────────────────

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 72

# ── Pydantic schemas ─────────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str


class TokenResponse(BaseModel):
    token: str
    user: UserOut


# ── Database setup ────────────────────────────────────────────────────────────


def init_users_table():
    """Create the users table if it doesn't already exist."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                email         TEXT    UNIQUE NOT NULL,
                password_hash TEXT    NOT NULL,
                first_name    TEXT    NOT NULL,
                last_name     TEXT    NOT NULL,
                created_at    TEXT    NOT NULL
            )
        """)
        conn.commit()


# ── User CRUD ─────────────────────────────────────────────────────────────────


def create_user(email: str, password: str, first_name: str, last_name: str) -> UserOut:
    """Register a new user. Raises ValueError if email already exists."""
    password_hash = _hash_password(password)
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (email, password_hash, first_name, last_name, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (email.lower().strip(), password_hash, first_name.strip(), last_name.strip(), created_at),
            )
            conn.commit()
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError("An account with this email already exists.")

    return UserOut(id=user_id, email=email.lower().strip(), first_name=first_name.strip(), last_name=last_name.strip())


def authenticate_user(email: str, password: str) -> Optional[UserOut]:
    """Verify email + password. Returns UserOut or None."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, email, password_hash, first_name, last_name FROM users WHERE email = ?",
            (email.lower().strip(),),
        ).fetchone()

    if not row:
        return None
    if not _verify_password(password, row["password_hash"]):
        return None

    return UserOut(id=row["id"], email=row["email"], first_name=row["first_name"], last_name=row["last_name"])


def get_user_by_id(user_id: int) -> Optional[UserOut]:
    """Lookup user by ID for JWT validation."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, email, first_name, last_name FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

    if not row:
        return None
    return UserOut(id=row["id"], email=row["email"], first_name=row["first_name"], last_name=row["last_name"])


# ── JWT helpers ───────────────────────────────────────────────────────────────


def create_access_token(user_id: int) -> str:
    """Create a JWT token with 72-hour expiry."""
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[int]:
    """Decode a JWT token. Returns user_id or None if invalid/expired."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
