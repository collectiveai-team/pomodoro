"""Shared row-mapping helpers for `database/*_repository.py` modules (CES-18).

Every repository converts a persisted SQLModel row to a `core.entities`
dataclass after an insert-or-fetch, when the row's auto-increment primary key
is guaranteed to already be set. `require_id` makes that invariant explicit in
one place instead of each repository re-deriving its own null check.
"""

from __future__ import annotations


def require_id(row_id: int | None) -> int:
    """Return `row_id`, raising if a persisted row somehow still lacks one."""
    if row_id is None:
        raise RuntimeError("Row has no primary key after persistence.")
    return row_id
