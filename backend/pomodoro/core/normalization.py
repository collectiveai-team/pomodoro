"""The single comparison-key normalization rule (issue #12 spec).

`normalize()` is the one place `strip().casefold()` is written. Task `text_key`,
Tag `name_key` and User `email_key` all call it so " Trabajo ", "TRABAJO" and
"trabajo" collide in every uniqueness check, everywhere, without a second
implementation drifting out of sync with this one.
"""

from __future__ import annotations


def normalize(value: str) -> str:
    """Return the case- and whitespace-insensitive comparison key for `value`."""
    return value.strip().casefold()


def task_text_key(text: str) -> str:
    """Return the comparison key for a Task's `text`."""
    return normalize(text)


def tag_name_key(name: str) -> str:
    """Return the comparison key for a Tag's `name`."""
    return normalize(name)


def user_email_key(email: str) -> str:
    """Return the comparison key for a User's `email`."""
    return normalize(email)
