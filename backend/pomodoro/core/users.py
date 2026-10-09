"""The `User` entity, its domain errors, and the repository Protocol it needs.

`User` carries no password: hashing is a `core.passwords` concern, and the password hash is a
persistence-only column `UserRepository` accepts and stores but never exposes back as part of
the entity (ADR-0001: core holds domain rules, not secrets).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, NewType, Protocol
from uuid import UUID

from email_validator import EmailNotValidError, validate_email

if TYPE_CHECKING:
    from datetime import datetime

UserId = NewType("UserId", UUID)

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128


class InvalidEmailError(ValueError):
    """Raised when an email does not look like a valid address."""


class DuplicateEmailError(ValueError):
    """Raised when an email is already registered, compared by its normalized `email_key`."""


class InvalidPasswordLengthError(ValueError):
    """Raised when a password is shorter than 8 or longer than 128 characters."""


class InvalidCredentialsError(ValueError):
    """Raised on any login mismatch; the message never reveals which field was wrong."""


@dataclass(frozen=True, slots=True)
class User:
    """A registered User: identity, normalized email key, time zone, and preferences."""

    id: UserId
    email: str
    email_key: str
    time_zone: str
    alarm_enabled: bool
    notifications_enabled: bool
    created_at: datetime


@dataclass(frozen=True, slots=True)
class UserCredentials:
    """A User alongside its stored Argon2 hash, for login's password check only."""

    user: User
    password_hash: str


def normalize_email(email: str) -> str:
    """Return the comparison key for an email: `strip().casefold()`."""
    return email.strip().casefold()


def validate_email_format(email: str) -> None:
    """Raise `InvalidEmailError` unless `email` is a well-formed address."""
    try:
        validate_email(email.strip(), check_deliverability=False)
    except EmailNotValidError as exc:
        raise InvalidEmailError(f"'{email}' is not a valid email address.") from exc


def validate_password_length(password: str) -> None:
    """Raise `InvalidPasswordLengthError` unless `password`'s length is 8..128 characters."""
    if not (MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH):
        raise InvalidPasswordLengthError(
            f"Password must be between {MIN_PASSWORD_LENGTH} and {MAX_PASSWORD_LENGTH} characters."
        )


class UserRepository(Protocol):
    """Persistence Protocol for `User`, implemented by `database.repositories.user`."""

    def add(self, user: User, password_hash: str) -> None:
        """Persist a new User together with its Argon2 password hash."""
        ...

    def get_by_email_key(self, email_key: str) -> User | None:
        """Return the User whose normalized email key matches `email_key`, or None."""
        ...

    def get_by_id(self, user_id: UserId) -> User | None:
        """Return the User with this id, or None."""
        ...

    def get_credentials_by_email_key(self, email_key: str) -> UserCredentials | None:
        """Return the User and stored password hash whose email key matches, or None."""
        ...
