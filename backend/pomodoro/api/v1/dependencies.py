"""Shared API dependency providers whose concrete adapters are wired by `entrypoints`."""

from __future__ import annotations

from typing import cast

from fastapi import Request

from pomodoro.core.clock import Clock


def get_clock(request: Request) -> Clock:
    """Return the Clock injected by the app factory, without leaking its adapter into `core`."""
    return cast("Clock", request.app.state.clock)
