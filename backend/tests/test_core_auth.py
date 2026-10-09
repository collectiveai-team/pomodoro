"""Tests for core auth (password hashing, email validation) and the T7 repositories."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from sqlmodel import Session

from pomodoro.core.auth import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    email_key,
    hash_password,
    normalize_email,
    verify_password,
)
from pomodoro.core.entities import AuthSession, UserId
from pomodoro.core.errors import DuplicateEmailError, EmailInvalidError, PasswordLengthError
from pomodoro.database.auth_session_repository import SqlAuthSessionRepository
from pomodoro.database.engine import build_engine
from pomodoro.database.tables import SQLModel
from pomodoro.database.user_repository import SqlUserRepository

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.engine import Engine

pytestmark = pytest.mark.unit

_VALID_PASSWORD = "correct horse battery staple"


@pytest.fixture
def engine() -> Iterator[Engine]:
    engine = build_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as session:
        yield session


class TestHashPassword:
    def test_hash_then_verify_round_trips(self) -> None:
        password_hash = hash_password(_VALID_PASSWORD)
        assert verify_password(_VALID_PASSWORD, password_hash) is True

    def test_verify_rejects_a_wrong_password(self) -> None:
        password_hash = hash_password(_VALID_PASSWORD)
        assert verify_password("wrong password entirely", password_hash) is False

    def test_hash_never_equals_the_raw_password(self) -> None:
        password_hash = hash_password(_VALID_PASSWORD)
        assert password_hash != _VALID_PASSWORD

    def test_rejects_a_password_shorter_than_the_minimum(self) -> None:
        with pytest.raises(PasswordLengthError) as exc_info:
            hash_password("short1")
        assert "short1" not in str(exc_info.value)
        assert str(MIN_PASSWORD_LENGTH) in str(exc_info.value)

    def test_rejects_a_password_longer_than_the_maximum(self) -> None:
        too_long = "a" * (MAX_PASSWORD_LENGTH + 1)
        with pytest.raises(PasswordLengthError) as exc_info:
            hash_password(too_long)
        assert too_long not in str(exc_info.value)

    def test_accepts_passwords_at_each_length_boundary(self) -> None:
        hash_password("a" * MIN_PASSWORD_LENGTH)
        hash_password("a" * MAX_PASSWORD_LENGTH)


class TestEmailNormalization:
    def test_normalizes_a_valid_email(self) -> None:
        assert normalize_email("Someone@EXAMPLE.com") == "Someone@example.com"

    def test_rejects_a_syntactically_invalid_email(self) -> None:
        with pytest.raises(EmailInvalidError):
            normalize_email("not-an-email")

    @pytest.mark.parametrize(
        "variant", ["Someone@example.com", "someone@example.com", " SOMEONE@EXAMPLE.COM "]
    )
    def test_differently_cased_or_spaced_emails_share_the_same_comparison_key(
        self, variant: str
    ) -> None:
        assert email_key(variant) == email_key("someone@example.com")


class TestUserRepository:
    def test_add_persists_a_user_and_returns_a_dataclass_without_the_password(
        self, session: Session
    ) -> None:
        repo = SqlUserRepository(session)
        created_at = datetime.now(UTC)

        user = repo.add(
            email="Someone@example.com",
            password_hash=hash_password(_VALID_PASSWORD),
            time_zone="UTC",
            created_at=created_at,
        )

        assert user.email == "Someone@example.com"
        assert user.time_zone == "UTC"
        assert not hasattr(user, "password_hash")

    def test_get_by_id_returns_the_same_user(self, session: Session) -> None:
        repo = SqlUserRepository(session)
        created = repo.add(
            email="a@example.com",
            password_hash=hash_password(_VALID_PASSWORD),
            time_zone="UTC",
            created_at=datetime.now(UTC),
        )

        fetched = repo.get_by_id(created.id)

        assert fetched == created

    def test_get_by_id_returns_none_for_an_unknown_user(self, session: Session) -> None:
        repo = SqlUserRepository(session)
        assert repo.get_by_id(UserId(9999)) is None

    def test_get_by_email_is_case_and_whitespace_insensitive(self, session: Session) -> None:
        repo = SqlUserRepository(session)
        created = repo.add(
            email="Someone@example.com",
            password_hash=hash_password(_VALID_PASSWORD),
            time_zone="UTC",
            created_at=datetime.now(UTC),
        )

        fetched = repo.get_by_email(" SOMEONE@EXAMPLE.COM ")

        assert fetched == created

    def test_add_rejects_a_normalized_duplicate_email(self, session: Session) -> None:
        repo = SqlUserRepository(session)
        repo.add(
            email="Someone@example.com",
            password_hash=hash_password(_VALID_PASSWORD),
            time_zone="UTC",
            created_at=datetime.now(UTC),
        )

        with pytest.raises(DuplicateEmailError):
            repo.add(
                email="someone@example.com",
                password_hash=hash_password(_VALID_PASSWORD),
                time_zone="UTC",
                created_at=datetime.now(UTC),
            )

    def test_get_password_hash_returns_the_stored_hash_not_the_user(self, session: Session) -> None:
        repo = SqlUserRepository(session)
        password_hash = hash_password(_VALID_PASSWORD)
        created = repo.add(
            email="a@example.com",
            password_hash=password_hash,
            time_zone="UTC",
            created_at=datetime.now(UTC),
        )

        stored_hash = repo.get_password_hash(created.id)
        assert stored_hash == password_hash
        assert stored_hash is not None
        assert verify_password(_VALID_PASSWORD, stored_hash)

    def test_update_persists_preference_changes(self, session: Session) -> None:
        repo = SqlUserRepository(session)
        created = repo.add(
            email="a@example.com",
            password_hash=hash_password(_VALID_PASSWORD),
            time_zone="UTC",
            created_at=datetime.now(UTC),
        )

        updated = repo.update(replace(created, time_zone="America/Bogota", alarm_enabled=False))

        assert updated.time_zone == "America/Bogota"
        assert updated.alarm_enabled is False
        refetched = repo.get_by_id(created.id)
        assert refetched is not None
        assert refetched.time_zone == "America/Bogota"

    def test_update_password_hash_replaces_the_stored_hash(self, session: Session) -> None:
        repo = SqlUserRepository(session)
        created = repo.add(
            email="a@example.com",
            password_hash=hash_password(_VALID_PASSWORD),
            time_zone="UTC",
            created_at=datetime.now(UTC),
        )
        new_hash = hash_password("a different correct horse battery")

        repo.update_password_hash(created.id, new_hash)

        assert repo.get_password_hash(created.id) == new_hash

    def test_delete_removes_the_user(self, session: Session) -> None:
        repo = SqlUserRepository(session)
        created = repo.add(
            email="a@example.com",
            password_hash=hash_password(_VALID_PASSWORD),
            time_zone="UTC",
            created_at=datetime.now(UTC),
        )

        repo.delete(created.id)

        assert repo.get_by_id(created.id) is None


class TestAuthSessionRepository:
    def _make_user(self, session: Session, *, email: str = "a@example.com") -> UserId:
        user = SqlUserRepository(session).add(
            email=email,
            password_hash=hash_password(_VALID_PASSWORD),
            time_zone="UTC",
            created_at=datetime.now(UTC),
        )
        return user.id

    def _add_session(
        self, session: Session, *, user_id: UserId, token_hash: str = "hash-of-token"
    ) -> AuthSession:
        now = datetime.now(UTC)
        return SqlAuthSessionRepository(session).add(
            user_id=user_id,
            token_hash=token_hash,
            created_at=now,
            last_used_at=now,
            expires_at=now + timedelta(days=30),
        )

    def test_add_persists_a_session_and_returns_a_dataclass(self, session: Session) -> None:
        user_id = self._make_user(session)

        created = self._add_session(session, user_id=user_id)

        assert created.user_id == user_id
        assert created.token_hash == "hash-of-token"

    def test_get_by_token_hash_returns_the_matching_session(self, session: Session) -> None:
        user_id = self._make_user(session)
        created = self._add_session(session, user_id=user_id)

        fetched = SqlAuthSessionRepository(session).get_by_token_hash("hash-of-token")

        assert fetched == created

    def test_get_by_token_hash_returns_none_for_an_unknown_token(self, session: Session) -> None:
        repo = SqlAuthSessionRepository(session)
        assert repo.get_by_token_hash("unknown") is None

    def test_update_persists_sliding_expiry_renewal(self, session: Session) -> None:
        user_id = self._make_user(session)
        created = self._add_session(session, user_id=user_id)
        repo = SqlAuthSessionRepository(session)

        renewed_last_used = created.last_used_at + timedelta(days=1)
        renewed_expiry = renewed_last_used + timedelta(days=30)
        updated = repo.update(
            replace(created, last_used_at=renewed_last_used, expires_at=renewed_expiry)
        )

        assert updated.last_used_at == renewed_last_used
        assert updated.expires_at == renewed_expiry

    def test_delete_revokes_a_single_session(self, session: Session) -> None:
        user_id = self._make_user(session)
        created = self._add_session(session, user_id=user_id)
        repo = SqlAuthSessionRepository(session)

        repo.delete(created.id)

        assert repo.get_by_token_hash("hash-of-token") is None

    def test_delete_all_for_user_revokes_every_session_for_that_user_only(
        self, session: Session
    ) -> None:
        user_id = self._make_user(session)
        other_user_id = self._make_user(session, email="other@example.com")
        self._add_session(session, user_id=user_id, token_hash="token-a")
        self._add_session(session, user_id=user_id, token_hash="token-b")
        other_session = self._add_session(session, user_id=other_user_id, token_hash="token-c")
        repo = SqlAuthSessionRepository(session)

        repo.delete_all_for_user(user_id)

        assert repo.get_by_token_hash("token-a") is None
        assert repo.get_by_token_hash("token-b") is None
        assert repo.get_by_token_hash("token-c") == other_session
