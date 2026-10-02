# SQLModel + Alembic over SQLite (local) and PostgreSQL (production)

The web app runs on SQLite locally and on PostgreSQL in production, with real user data that will need schema changes, so queries must be portable across two dialects and migrations must be real from day one. We chose SQLModel (SQLAlchemy 2 underneath) with Alembic migrations that run against both engines, selected by a `DATABASE_URL` setting. Hand-written SQL over stdlib `sqlite3` was rejected because dialect-specific functions (SQLite's `strftime(..., 'localtime')`, text dates) have no PostgreSQL equivalent and migrations would be home-grown. Dates are stored as timezone-aware UTC timestamps, and History groups each Pomodoro by the day it ended in the User's stored time zone, computed portably rather than with engine-specific functions.

SQLModel classes are confined to the `database` layer. `core` keeps plain dataclasses and `api` keeps its own Pydantic schemas, even though SQLModel invites reusing one class as table, entity and HTTP schema: that would leak internal columns (e.g. `text_key`) into the API and break the import-linter layer contract.

## Consequences

- Every user-owned table carries a `user_id`; uniqueness rules (Active Task text, Tag name) are per-User composite constraints.
- Unit tests use SQLite `:memory:`; dialect parity is covered by `integration` tests against a real PostgreSQL service container in CI.
