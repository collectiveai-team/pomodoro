"""Argon2 password hashing (`pwdlib`), used by the auth use cases.

Passwords and their hashes are never logged (CES-45/46): this module only ever returns a hash
string and a boolean, never anything a caller might be tempted to pass to `get_logger`.
"""

from __future__ import annotations

from pwdlib import PasswordHash

_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash `password` with Argon2 (pwdlib's recommended scheme)."""
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Return whether `password` matches the stored Argon2 `password_hash`."""
    return _password_hash.verify(password, password_hash)
