"""Password hashing, email/password validation, and session-token helpers.

Pure core: `pwdlib` and `email_validator` are leaf crypto/validation libraries
with no framework or network dependency of their own (deliverability DNS
lookups are explicitly disabled below), so depending on them here does not
violate the no-fastapi/sqlmodel/pydantic rule.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from hashlib import sha256
from typing import TYPE_CHECKING
from zoneinfo import available_timezones

from email_validator import EmailNotValidError
from email_validator import validate_email as _validate_email_syntax
from pwdlib import PasswordHash

from pomodoro.core.errors import InvalidEmailError, InvalidPasswordLengthError, InvalidTimeZoneError

if TYPE_CHECKING:
    from pomodoro.core.entities import User

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
SESSION_TOKEN_BYTES = 32

_password_hash = PasswordHash.recommended()


@dataclass(frozen=True)
class UserRecord:
    """A persisted User paired with its Argon2 password hash.

    Exists only so a login/duplicate-check lookup can reach the hash; the
    hash never appears on the `User` entity itself and must never cross the
    `api` boundary.
    """

    user: User
    password_hash: str


def validate_email_format(email: str) -> str:
    """Return the normalized email, or raise `InvalidEmailError` if malformed.

    `check_deliverability=False` keeps this offline: it validates syntax and
    domain shape only, never a DNS lookup.
    """
    try:
        result = _validate_email_syntax(email.strip(), check_deliverability=False)
    except EmailNotValidError as error:
        raise InvalidEmailError from error
    return result.normalized


def validate_password_length(password: str) -> None:
    """Raise `InvalidPasswordLengthError` unless length is within [8, 128].

    No composition rules (digits/symbols/casing) beyond length.
    """
    if not (MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH):
        raise InvalidPasswordLengthError


def validate_time_zone(time_zone: str) -> None:
    """Raise `InvalidTimeZoneError` unless `time_zone` is a real IANA zone name."""
    if time_zone not in available_timezones():
        raise InvalidTimeZoneError


def hash_password(password: str) -> str:
    """Return the Argon2 hash of `password`. Never log or return this across `api`."""
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Return whether `password` matches `password_hash`."""
    return _password_hash.verify(password, password_hash)


def generate_session_token() -> str:
    """Return a cryptographically random, URL-safe opaque session token."""
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


def hash_session_token(token: str) -> str:
    """Return the deterministic digest stored and looked up for a session token.

    The token already carries 256 bits of entropy from `secrets`, so a fast
    deterministic digest (not Argon2) is appropriate: it only needs to resist
    reversal, not offline guessing of a user-chosen secret.
    """
    return sha256(token.encode("utf-8")).hexdigest()
