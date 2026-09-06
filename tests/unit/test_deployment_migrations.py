"""Regression checks for fail-safe production migration commands."""

from pathlib import Path


def test_deployment_does_not_ignore_migration_failures() -> None:
    root = Path(__file__).parents[2]
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    railway = (root / "railway.toml").read_text(encoding="utf-8")

    assert "alembic upgrade head || true" not in dockerfile
    assert "alembic upgrade head || true" not in railway
    assert "alembic upgrade head && exec uvicorn" in dockerfile
    assert "alembic upgrade head && exec uvicorn" in railway
