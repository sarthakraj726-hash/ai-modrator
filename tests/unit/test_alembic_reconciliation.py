"""Automated regression tests for Alembic graph reconciliation and legacy revision 002_add_join_message_sent."""

import asyncio
import os
import sqlite3
import tempfile
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.session as session_module
from alembic import command
from app.core.config import get_settings
from app.db.models.creator import Creator
from app.db.models.stream_session import StreamSession
from app.db.session import init_db_engine


@pytest.fixture
def temp_db_path() -> Generator[str, None, None]:
    """Provide a temporary database file path and clean up afterward."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    if os.path.exists(path):
        os.remove(path)
    yield path
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


def _run_upgrade_sync(cfg: Config, target: str = "head") -> None:
    """Execute alembic upgrade in a dedicated thread to avoid event loop conflicts."""
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(command.upgrade, cfg, target)
        future.result()


def test_alembic_graph_has_single_head_and_resolves_all_revisions() -> None:
    """The migration graph must have exactly one head and zero broken revision links."""
    root = Path(__file__).parents[2]
    cfg = Config(str(root / "alembic.ini"))
    script = ScriptDirectory.from_config(cfg)

    heads = script.get_heads()
    assert len(heads) == 1, f"Expected exactly 1 head, found: {heads}"
    assert heads[0] == "0009_reconcile_legacy_history"

    bases = script.get_bases()
    assert "0001_initial_schema" in bases
    assert "002_add_join_message_sent" in bases

    # Verify walk_revisions reaches all revisions from head to base without resolution error
    all_revisions = [rev.revision for rev in script.walk_revisions()]
    assert "0009_reconcile_legacy_history" in all_revisions
    assert "0008_reconcile_missing_core_tables" in all_revisions
    assert "0007_create_monitored_channels" in all_revisions
    assert "0006_reconcile_production_schema" in all_revisions
    assert "0005_phase5_operations_incidents" in all_revisions
    assert "0004_phase4_engagement_economy" in all_revisions
    assert "0003_phase3_ai_moderation_persona" in all_revisions
    assert "0002_phase2_youtube_websub" in all_revisions
    assert "0001_initial_schema" in all_revisions
    assert "002_add_join_message_sent" in all_revisions


def test_upgrade_from_scratch_reaches_head(temp_db_path: str) -> None:
    """A fresh database must upgrade from <base> directly to the merge head."""
    root = Path(__file__).parents[2]
    db_uri = f"sqlite+aiosqlite:///{temp_db_path}"

    os.environ["DATABASE_URL"] = db_uri
    get_settings.cache_clear()

    cfg = Config(str(root / "alembic.ini"))
    _run_upgrade_sync(cfg, "head")

    # Verify alembic_version table has 0009_reconcile_legacy_history
    conn = sqlite3.connect(temp_db_path)
    cur = conn.cursor()
    cur.execute("SELECT version_num FROM alembic_version")
    rows = cur.fetchall()
    assert rows == [("0009_reconcile_legacy_history",)]

    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cur.fetchall()}
    conn.close()

    expected_tables = {
        "creators",
        "stream_sessions",
        "audit_events",
        "system_events",
        "youtube_websub_subscriptions",
        "moderation_reviews",
        "economy_accounts",
        "economy_transactions",
        "economy_ledger_entries",
        "incidents",
        "feature_flags",
        "monitored_channels",
    }
    for table in expected_tables:
        assert table in tables, f"Expected table '{table}' missing from upgraded schema"


def test_upgrade_from_legacy_002_add_join_message_sent_succeeds(temp_db_path: str) -> None:
    """A database starting at '002_add_join_message_sent' must safely upgrade to head."""
    # Seed isolated database with historical production state
    conn = sqlite3.connect(temp_db_path)
    conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)")
    conn.execute("INSERT INTO alembic_version (version_num) VALUES ('002_add_join_message_sent')")
    conn.commit()
    conn.close()

    root = Path(__file__).parents[2]
    db_uri = f"sqlite+aiosqlite:///{temp_db_path}"

    os.environ["DATABASE_URL"] = db_uri
    get_settings.cache_clear()

    cfg = Config(str(root / "alembic.ini"))
    # Upgrade must not raise 'Can't locate revision identified by 002_add_join_message_sent'
    _run_upgrade_sync(cfg, "head")

    conn = sqlite3.connect(temp_db_path)
    cur = conn.cursor()
    cur.execute("SELECT version_num FROM alembic_version")
    rows = cur.fetchall()
    assert rows == [("0009_reconcile_legacy_history",)]

    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cur.fetchall()}
    conn.close()

    assert "stream_sessions" in tables
    assert "creators" in tables
    assert "monitored_channels" in tables
    assert "feature_flags" in tables


def test_migration_re_run_is_idempotent(temp_db_path: str) -> None:
    """Running 'alembic upgrade head' consecutively must succeed as a no-op."""
    root = Path(__file__).parents[2]
    db_uri = f"sqlite+aiosqlite:///{temp_db_path}"

    os.environ["DATABASE_URL"] = db_uri
    get_settings.cache_clear()

    cfg = Config(str(root / "alembic.ini"))
    _run_upgrade_sync(cfg, "head")
    # Second run
    _run_upgrade_sync(cfg, "head")

    conn = sqlite3.connect(temp_db_path)
    cur = conn.cursor()
    cur.execute("SELECT version_num FROM alembic_version")
    rows = cur.fetchall()
    assert rows == [("0009_reconcile_legacy_history",)]
    conn.close()


@pytest.mark.asyncio
async def test_init_db_engine_succeeds_from_legacy_production_state(temp_db_path: str) -> None:
    """FastAPI startup lifespan (init_db_engine) must cleanly initialize from legacy state."""
    # Seed database with historical state
    conn = sqlite3.connect(temp_db_path)
    conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)")
    conn.execute("INSERT INTO alembic_version (version_num) VALUES ('002_add_join_message_sent')")
    conn.commit()
    conn.close()

    db_uri = f"sqlite+aiosqlite:///{temp_db_path}"
    os.environ["DATABASE_URL"] = db_uri
    get_settings.cache_clear()

    # Reset engine and factory caches
    session_module._engine = None
    session_module._session_factory = None

    await init_db_engine()

    assert "alembic: upgraded to head" in session_module._schema_init_log

    # Verify default creator was seeded
    test_engine = create_async_engine(db_uri)
    async with test_engine.connect() as conn_async:
        result = await conn_async.execute(select(Creator.id).where(Creator.id == "default-creator"))
        assert result.scalar() == "default-creator"
    await test_engine.dispose()
    await session_module.close_db_engine()


@pytest.mark.asyncio
async def test_stream_sessions_join_message_sent_column_compatibility(temp_db_path: str) -> None:
    """If 'join_message_sent' exists in stream_sessions table, StreamSession queries remain valid."""
    root = Path(__file__).parents[2]
    db_uri = f"sqlite+aiosqlite:///{temp_db_path}"

    os.environ["DATABASE_URL"] = db_uri
    get_settings.cache_clear()

    cfg = Config(str(root / "alembic.ini"))
    await asyncio.to_thread(_run_upgrade_sync, cfg, "head")

    # Manually add join_message_sent if not already added
    conn = sqlite3.connect(temp_db_path)
    try:
        conn.execute("ALTER TABLE stream_sessions ADD COLUMN join_message_sent BOOLEAN DEFAULT 0")
        conn.commit()
    except Exception:
        pass
    conn.close()

    # Query StreamSession through SQLAlchemy model
    test_engine = create_async_engine(db_uri)
    async with test_engine.connect() as conn_async:
        # Insert a dummy creator and stream session
        await conn_async.execute(
            text(
                "INSERT INTO creators (id, youtube_channel_id, channel_name, enabled, created_at, updated_at) "
                "VALUES ('c1', 'UC1', 'Ch1', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
        await conn_async.execute(
            text(
                "INSERT INTO stream_sessions (id, creator_id, youtube_video_id, status, created_at, updated_at) "
                "VALUES ('s1', 'c1', 'v1', 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
        await conn_async.commit()

        result = await conn_async.execute(
            select(StreamSession.id, StreamSession.youtube_video_id).where(StreamSession.id == "s1")
        )
        row = result.first()
        assert row is not None
        assert row[0] == "s1"
        assert row[1] == "v1"

    await test_engine.dispose()
