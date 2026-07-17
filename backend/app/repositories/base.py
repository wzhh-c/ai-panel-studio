"""Base repository with generic CRUD operations.

All repositories inherit from this class and share a connection factory
(defaulting to ``get_db_connection`` from ``database.py``).
"""

import logging
from contextlib import contextmanager
from typing import Any, Callable, Optional

import sqlite3

from app.database import get_db_connection
from app.exceptions import DuplicateRecordError, ForeignKeyError

logger = logging.getLogger(__name__)

ConnectionFactory = Callable[..., Any]
"""A callable that returns a context manager yielding a sqlite3.Connection."""


class BaseRepository:
    """Generic repository providing CRUD helpers for a SQLite table.

    Args:
        connection_factory: A callable that yields a sqlite3.Connection.
            Defaults to ``get_db_connection``. Inject a different factory
            (e.g. in-memory) for testing.
    """

    def __init__(
        self,
        connection_factory: Optional[ConnectionFactory] = None,
    ) -> None:
        self._connection_factory: ConnectionFactory = (
            connection_factory or get_db_connection
        )

    # ── helpers ────────────────────────────────────────────────

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        """Convert a sqlite3.Row to a plain dict."""
        return dict(row)

    @staticmethod
    def _handle_integrity_error(exc: sqlite3.IntegrityError) -> None:
        """Map a sqlite3.IntegrityError to a domain-specific exception."""
        msg = str(exc).lower()
        if "unique" in msg or "primary key" in msg:
            raise DuplicateRecordError(str(exc)) from exc
        if "foreign key" in msg:
            raise ForeignKeyError(str(exc)) from exc
        raise

    # ── CRUD ───────────────────────────────────────────────────

    def get_by_id(self, record_id: str, table_name: str) -> Optional[dict[str, Any]]:
        """Return a single row as a dict, or ``None`` if not found.

        Args:
            record_id: Primary-key value.
            table_name: Target table name (unquoted, assumed safe).

        Returns:
            Row dict or ``None``.
        """
        with self._connection_factory() as conn:
            cursor = conn.execute(
                f'SELECT * FROM "{table_name}" WHERE id = ?', (record_id,)
            )
            row = cursor.fetchone()
            return self._row_to_dict(row) if row else None

    def list_all(
        self, table_name: str, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Return a paginated list of rows.

        Args:
            table_name: Target table name.
            limit: Maximum rows to return.
            offset: Rows to skip.

        Returns:
            List of row dicts.
        """
        with self._connection_factory() as conn:
            cursor = conn.execute(
                f'SELECT * FROM "{table_name}" LIMIT ? OFFSET ?', (limit, offset)
            )
            return [self._row_to_dict(row) for row in cursor.fetchall()]

    def delete(self, record_id: str, table_name: str) -> bool:
        """Delete a row by primary key.

        Args:
            record_id: Primary-key value.
            table_name: Target table name.

        Returns:
            ``True`` if a row was deleted, ``False`` otherwise.
        """
        with self._connection_factory() as conn:
            cursor = conn.execute(
                f'DELETE FROM "{table_name}" WHERE id = ?', (record_id,)
            )
            deleted = cursor.rowcount > 0
            logger.debug("Deleted %s from %s: %s", record_id, table_name, deleted)
            return deleted
