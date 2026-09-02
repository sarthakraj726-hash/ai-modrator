"""Unit tests for application lifecycle hooks."""

import pytest

from app.core.lifecycle import lifespan
from app.main import app


@pytest.mark.asyncio
async def test_application_lifespan():
    async with lifespan(app):
        # Application started cleanly
        pass
    # Application shutdown cleanly
