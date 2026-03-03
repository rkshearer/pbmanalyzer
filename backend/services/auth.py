"""
Authentication service.
Handles user registration, login, and JWT token management.
"""

import hashlib
import os
import secrets
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


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


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
        # Migration: add reset token columns if they don't exist yet
        for col in ("reset_token TEXT", "reset_token_expires TEXT"):
            try:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col}")
            except sqlite3.OperationalError:
                pass  # Column already exists
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


# ── Password reset ────────────────────────────────────────────────────────────

def _hash_token(token: str) -> str:
    """SHA-256 hash a reset token for safe storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def create_reset_token(email: str) -> Optional[str]:
    """Generate a reset token for the given email. Returns None if email not found."""
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT id FROM users WHERE email = ?", (email.lower().strip(),)).fetchone()
        if not row:
            return None
        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_token(raw_token)
        expires = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "UPDATE users SET reset_token = ?, reset_token_expires = ? WHERE id = ?",
            (token_hash, expires, row[0]),
        )
        conn.commit()
    return raw_token


def validate_reset_token(token: str) -> Optional[int]:
    """Check if a reset token is valid and not expired. Returns user_id or None."""
    token_hash = _hash_token(token)
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, reset_token_expires FROM users WHERE reset_token = ?",
            (token_hash,),
        ).fetchone()
    if not row:
        return None
    expires = datetime.strptime(row["reset_token_expires"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires:
        return None
    return row["id"]


def reset_password(token: str, new_password: str) -> Optional[UserOut]:
    """Validate token, update password, clear token fields. Returns UserOut or None."""
    user_id = validate_reset_token(token)
    if user_id is None:
        return None
    password_hash = _hash_password(new_password)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, reset_token = NULL, reset_token_expires = NULL WHERE id = ?",
            (password_hash, user_id),
        )
        conn.commit()
    return get_user_by_id(user_id)


def send_reset_email(email: str, token: str) -> None:
    """Send a password reset link via Resend API."""
    import requests as _requests

    api_key = os.getenv("RESEND_API_KEY", "").strip()
    from_address = os.getenv("NOTIFY_FROM", "PBM Analyzer <onboarding@resend.dev>")
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")

    if not api_key:
        return  # Not configured — skip silently

    reset_link = f"{frontend_url}?reset_token={token}"

    body_html = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                max-width:520px;margin:0 auto;">
      <div style="background:#1e3a5f;padding:20px 28px;border-radius:8px 8px 0 0;">
        <h2 style="color:#fff;margin:0;font-size:18px;">PBM Contract Analyzer</h2>
      </div>
      <div style="background:#ffffff;padding:28px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 8px 8px;">
        <p style="margin:0 0 16px;color:#0f172a;">You requested a password reset. Click the button below to set a new password:</p>
        <a href="{reset_link}"
           style="display:inline-block;background:#1e3a5f;color:#fff;padding:12px 28px;
                  border-radius:6px;text-decoration:none;font-weight:600;font-size:15px;">
          Reset Password
        </a>
        <p style="margin:16px 0 0;color:#64748b;font-size:13px;">
          This link expires in 1 hour. If you didn't request this, you can safely ignore this email.
        </p>
      </div>
    </div>
    """

    _requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "from": from_address,
            "to": [email],
            "subject": "Reset your PBM Analyzer password",
            "html": body_html,
        },
        timeout=10,
    )
