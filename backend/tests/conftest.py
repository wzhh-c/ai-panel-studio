# -*- coding: utf-8 -*-
"""Pytest configuration — environment variables and shared fixtures."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import pytest

# Must be set BEFORE any app modules are imported.
os.environ.setdefault("DEEPSEEK_API_KEY", "test-dummy-key")
os.environ.setdefault("USE_MOCK_LLM", "true")


def _load_schema() -> str:
    schema_path = (
        Path(__file__).resolve().parent.parent / "docs" / "schema.sql"
    )
    return schema_path.read_text(encoding="utf-8")


@pytest.fixture(scope="function")
def in_memory_db():
    """Provide an in-memory SQLite connection that can be shared across
    threads (needed by TestClient which runs in a worker thread)."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_load_schema())

    @contextmanager
    def factory() -> Generator[sqlite3.Connection, None, None]:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    yield factory, conn
    conn.close()


@pytest.fixture(scope="function")
def seed_user(in_memory_db):
    """Seed a default user into the in-memory database."""
    _, conn = in_memory_db
    conn.execute(
        'INSERT INTO "user" (id, name) VALUES (?, ?)',
        ("550e8400-e29b-41d4-a716-446655440001", "Alice"),
    )
    conn.commit()
