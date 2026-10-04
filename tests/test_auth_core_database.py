"""Unit tests for Argon2 hashing/validation and the SQLModel-backed auth repositories."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from pomodoro.core.auth import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    UserRecord,
    generate_session_token,
    hash_password,
    hash_session_token,
    validate_email_format,
    validate_password_length,
    verify_password,
)
from pomodoro.core.entities import User, UserId
from pomodoro.core.errors import InvalidEmailError, InvalidPasswordLengthError
from pomodoro.core.normalization import normalize_key
from pomodoro.core.repositories import AuthSessionRepository, UserRepository
from pomodoro.database.auth_session_repository import SQLAuthSessionRepository
from pomodoro.database.engine import create_db_engine
from pomodoro.database.tables import SQLModel
from pomodoro.database.user_repository import SQLUserRepository

NOW = datetime(2026, 1, 1, tzinfo=UTC)


@dataclass
class FakeClock:
    """A `Clock` advanced by hand, standing in for the real wall clock in tests."""

    current: datetime = NOW

    def now(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> datetime:
        self.current += timedelta(seconds=seconds)
        return self.current


def _engine():
    engine = create_db_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


def make_user(*, email: str = "person@example.com", created_at: datetime = NOW) -> User:
    key = normalize_key(email)
    return User(
        id=UserId(0),
        email=email,
        email_key=key,
        created_at=created_at,
        time_zone="UTC",
        alarm_enabled=True,
        notifications_enabled=True,
    )


# --- hash_password / verify_password -------------------------------------------


def test_hash_password_round_trips_through_verify_password() -> None:
    hashed = hash_password("correct horse battery")
    assert verify_password("correct horse battery", hashed) is True


def test_verify_password_rejects_wrong_password() -> None:
    hashed = hash_password("correct horse battery")
    assert verify_password("wrong password", hashed) is False


def test_hash_password_never_returns_the_plaintext() -> None:
    hashed = hash_password("correct horse battery")
    assert "correct horse battery" not in hashed


# --- validate_email_format ------------------------------------------------------


def test_validate_email_format_accepts_and_normalizes_a_valid_email() -> None:
    assert validate_email_format("Person@Example.com") == "Person@example.com"


def test_validate_email_format_rejects_missing_at_sign() -> None:
    with pytest.raises(InvalidEmailError):
        validate_email_format("not-an-email")


def test_validate_email_format_rejects_embedded_whitespace() -> None:
    with pytest.raises(InvalidEmailError):
        validate_email_format("bad user@example.com")


def test_validate_email_format_does_not_hit_the_network() -> None:
    # A syntactically valid email at a domain with no mail records must still
    # pass: deliverability checking (DNS) must be disabled.
    assert (
        validate_email_format("person@nonexistent-domain-zzqx.example")
        == "person@nonexistent-domain-zzqx.example"
    )


# --- validate_password_length ---------------------------------------------------


def test_validate_password_length_accepts_minimum_boundary() -> None:
    validate_password_length("a" * MIN_PASSWORD_LENGTH)


def test_validate_password_length_accepts_maximum_boundary() -> None:
    validate_password_length("a" * MAX_PASSWORD_LENGTH)


def test_validate_password_length_rejects_below_minimum() -> None:
    with pytest.raises(InvalidPasswordLengthError):
        validate_password_length("a" * (MIN_PASSWORD_LENGTH - 1))


def test_validate_password_length_rejects_above_maximum() -> None:
    with pytest.raises(InvalidPasswordLengthError):
        validate_password_length("a" * (MAX_PASSWORD_LENGTH + 1))


def test_validate_password_length_has_no_composition_rules() -> None:
    validate_password_length("aaaaaaaa")


# --- generate_session_token / hash_session_token --------------------------------


def test_generate_session_token_returns_distinct_high_entropy_tokens() -> None:
    first = generate_session_token()
    second = generate_session_token()
    assert first != second
    assert len(first) >= 32


def test_hash_session_token_is_deterministic_and_never_equals_the_token() -> None:
    token = generate_session_token()
    assert hash_session_token(token) == hash_session_token(token)
    assert hash_session_token(token) != token


# --- SQLUserRepository -----------------------------------------------------------


def test_user_repository_satisfies_protocol() -> None:
    assert isinstance(SQLUserRepository(_engine()), UserRepository)


def test_user_repository_add_assigns_id_and_never_returns_the_hash() -> None:
    repo = SQLUserRepository(_engine())
    stored = repo.add(make_user(), password_hash="argon2-hash")
    assert stored.id != 0
    assert "argon2-hash" not in repr(stored)


def test_user_repository_get_by_id_round_trips() -> None:
    repo = SQLUserRepository(_engine())
    stored = repo.add(make_user(), password_hash="argon2-hash")
    fetched = repo.get_by_id(stored.id)
    assert fetched == stored


def test_user_repository_get_by_id_returns_none_when_absent() -> None:
    repo = SQLUserRepository(_engine())
    assert repo.get_by_id(UserId(999)) is None


def test_user_repository_get_by_email_key_returns_user_and_hash() -> None:
    repo = SQLUserRepository(_engine())
    stored = repo.add(make_user(email="Person@Example.com"), password_hash="argon2-hash")
    record = repo.get_by_email_key(normalize_key("Person@Example.com"))
    assert record == UserRecord(user=stored, password_hash="argon2-hash")


def test_user_repository_get_by_email_key_returns_none_when_absent() -> None:
    repo = SQLUserRepository(_engine())
    assert repo.get_by_email_key("nobody@example.com") is None


def test_user_repository_update_persists_changed_fields() -> None:
    repo = SQLUserRepository(_engine())
    stored = repo.add(make_user(), password_hash="argon2-hash")
    changed = User(
        id=stored.id,
        email=stored.email,
        email_key=stored.email_key,
        created_at=stored.created_at,
        time_zone="America/Argentina/Buenos_Aires",
        alarm_enabled=False,
        notifications_enabled=False,
    )
    updated = repo.update(changed)
    assert updated.time_zone == "America/Argentina/Buenos_Aires"
    assert updated.alarm_enabled is False
    assert repo.get_by_id(stored.id) == updated


def test_user_repository_delete_removes_the_user() -> None:
    repo = SQLUserRepository(_engine())
    stored = repo.add(make_user(), password_hash="argon2-hash")
    repo.delete(stored.id)
    assert repo.get_by_id(stored.id) is None


# --- SQLAuthSessionRepository -----------------------------------------------------


def test_auth_session_repository_satisfies_protocol() -> None:
    assert isinstance(SQLAuthSessionRepository(_engine(), FakeClock()), AuthSessionRepository)


def test_auth_session_repository_create_persists_only_the_token_hash() -> None:
    engine = _engine()
    user_repo = SQLUserRepository(engine)
    user = user_repo.add(make_user(), password_hash="argon2-hash")
    session_repo = SQLAuthSessionRepository(engine, FakeClock())

    expires_at = NOW + timedelta(days=30)
    session = session_repo.create(user.id, token_hash="tok-hash", expires_at=expires_at)

    assert session.id != 0
    assert session.token_hash == "tok-hash"
    assert session.created_at == NOW
    assert session.last_used_at == NOW
    assert session.expires_at == expires_at


def test_auth_session_repository_get_by_token_hash_round_trips() -> None:
    engine = _engine()
    user = SQLUserRepository(engine).add(make_user(), password_hash="argon2-hash")
    session_repo = SQLAuthSessionRepository(engine, FakeClock())
    created = session_repo.create(user.id, token_hash="tok-hash", expires_at=NOW)

    fetched = session_repo.get_by_token_hash("tok-hash")
    assert fetched == created


def test_auth_session_repository_get_by_token_hash_returns_none_when_absent() -> None:
    session_repo = SQLAuthSessionRepository(_engine(), FakeClock())
    assert session_repo.get_by_token_hash("missing") is None


def test_auth_session_repository_touch_last_used_renews_to_current_clock_time() -> None:
    engine = _engine()
    user = SQLUserRepository(engine).add(make_user(), password_hash="argon2-hash")
    clock = FakeClock()
    session_repo = SQLAuthSessionRepository(engine, clock)
    created = session_repo.create(user.id, token_hash="tok-hash", expires_at=NOW)

    clock.advance(3600)
    session_repo.touch_last_used(created.id)

    fetched = session_repo.get_by_token_hash("tok-hash")
    assert fetched is not None
    assert fetched.last_used_at == NOW + timedelta(seconds=3600)
    assert fetched.created_at == NOW  # unchanged


def test_auth_session_repository_revoke_deletes_only_that_session() -> None:
    engine = _engine()
    user = SQLUserRepository(engine).add(make_user(), password_hash="argon2-hash")
    session_repo = SQLAuthSessionRepository(engine, FakeClock())
    kept = session_repo.create(user.id, token_hash="keep", expires_at=NOW)
    revoked = session_repo.create(user.id, token_hash="revoke-me", expires_at=NOW)

    session_repo.revoke(revoked.id)

    assert session_repo.get_by_token_hash("revoke-me") is None
    assert session_repo.get_by_token_hash("keep") == kept


def test_auth_session_repository_revoke_all_for_user_clears_every_session() -> None:
    engine = _engine()
    user_repo = SQLUserRepository(engine)
    user_a = user_repo.add(make_user(email="a@example.com"), password_hash="hash-a")
    user_b = user_repo.add(make_user(email="b@example.com"), password_hash="hash-b")
    session_repo = SQLAuthSessionRepository(engine, FakeClock())
    session_repo.create(user_a.id, token_hash="a-1", expires_at=NOW)
    session_repo.create(user_a.id, token_hash="a-2", expires_at=NOW)
    other_user_session = session_repo.create(user_b.id, token_hash="b-1", expires_at=NOW)

    session_repo.revoke_all_for_user(user_a.id)

    assert session_repo.get_by_token_hash("a-1") is None
    assert session_repo.get_by_token_hash("a-2") is None
    assert session_repo.get_by_token_hash("b-1") == other_user_session
