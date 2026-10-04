"""Shared key normalization for task text, tag names, and email."""

from __future__ import annotations


def normalize_key(value: str) -> str:
    """Return the comparison key for case/whitespace-insensitive matching."""
    return value.strip().casefold()
