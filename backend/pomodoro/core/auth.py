"""Password hashing, email validation and session tokens (core, T7/T8).

Argon2 via pwdlib (the only hasher `PasswordHash.recommended()` resolves to with
the `argon2` extra installed); email normalization layers `email_validator`'s
syntax check on top of the shared `normalize()` comparison key (CES-16: one
normalization rule, never a second implementation). A raw password is never
logged or returned anywhere in this module, including from a raised error -
`PasswordLengthError` carries only the violated length bounds.

Login sessions (T8) use the same never-store-the-secret shape as passwords: a
session token is a cryptographically random opaque string handed to the
browser in a cookie, and only its SHA-256 hash is ever persisted
(`AuthSessionRepository.add`/`get_by_token_hash`), analogous to `password_hash`
never appearing on `User` itself.
"""

from __future__ import annotations

import hashlib
import secrets

from email_validator import EmailNotValidError, validate_email
from pwdlib import PasswordHash

from pomodoro.core.errors import EmailInvalidError, PasswordLengthError
from pomodoro.core.normalization import user_email_key

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
SESSION_TOKEN_BYTES = 32

_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash `password` with Argon2, after enforcing the 8-128 char length rule."""
    _validate_password_length(password)
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Return whether `password` matches the Argon2 `password_hash`."""
    return _password_hash.verify(password, password_hash)


def normalize_email(email: str) -> str:
    """Validate `email`'s syntax and return its normalized, storable form."""
    try:
        result = validate_email(email.strip(), check_deliverability=False)
    except EmailNotValidError as exc:
        raise EmailInvalidError(email) from exc
    return result.normalized


def email_key(email: str) -> str:
    """Return the shared comparison key for `email` (reuses core.normalization)."""
    return user_email_key(email)


def generate_session_token() -> str:
    """Return a new cryptographically random opaque session token (T8).

    Never persisted as-is; callers store only `hash_session_token(token)`.
    """
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


def hash_session_token(token: str) -> str:
    """Return the SHA-256 hex digest of `token` — the only form ever stored (T8)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _validate_password_length(password: str) -> None:
    length = len(password)
    if not MIN_PASSWORD_LENGTH <= length <= MAX_PASSWORD_LENGTH:
        raise PasswordLengthError(MIN_PASSWORD_LENGTH, MAX_PASSWORD_LENGTH)
