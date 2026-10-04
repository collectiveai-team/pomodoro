"""The FastAPI app factory and the bootable uvicorn entrypoint."""

import uvicorn
from fastapi import FastAPI

from pomodoro.api.health import get_clock
from pomodoro.api.health import router as health_router
from pomodoro.entrypoints.clock import RealClock
from pomodoro.entrypoints.settings import get_settings


def create_app() -> FastAPI:
    """Build the FastAPI app with real dependencies wired in."""
    app = FastAPI(title="Pomodoro Collective API")
    app.state.settings = get_settings()
    app.include_router(health_router)
    app.dependency_overrides[get_clock] = RealClock
    return app


app = create_app()


def main() -> None:
    """Run the app under uvicorn; the `pomodoro-api` console-script entrypoint."""
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
