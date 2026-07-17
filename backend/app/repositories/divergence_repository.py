"""Repository for the ``divergence`` table."""

import logging
from typing import Any, Optional

import sqlite3

from app.repositories.base import BaseRepository

logger = logging.getLogger(__name__)

TABLE = "divergence"

DIVERGENCE_COLUMNS = [
    "id",
    "content",
    "discussion_id",
    "sides",
    "source_transcript_ids",
    "created_at",
    "updated_at",
]


class DivergenceRepository(BaseRepository):
    """Data access for the ``divergence`` table."""

    # ── create ─────────────────────────────────────────────────

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Insert a divergence record and return it.

        Args:
            data: Column-value mapping. Must include ``id``, ``content``,
                ``discussion_id``, ``sides`` (JSON array string with ≥ 2
                elements), ``source_transcript_ids`` (JSON array string
                with ≥ 2 elements).

        Returns:
            The inserted row as a dict.

        Raises:
            ForeignKeyError: ``discussion_id`` does not exist.
            DuplicateRecordError: ``id`` already exists.
        """
        columns = [c for c in DIVERGENCE_COLUMNS if c in data]
        placeholders = ", ".join("?" for _ in columns)
        col_names = ", ".join(f'"{c}"' for c in columns)
        values = [data[c] for c in columns]

        with self._connection_factory() as conn:
            try:
                conn.execute(
                    f"INSERT INTO {TABLE} ({col_names}) VALUES ({placeholders})",
                    values,
                )
            except sqlite3.IntegrityError as exc:
                self._handle_integrity_error(exc)
            return self._fetch_by_id(conn, data["id"])

    # ── update ─────────────────────────────────────────────────

    def update(
        self,
        divergence_id: str,
        content: str,
        source_transcript_ids: str,
    ) -> Optional[dict[str, Any]]:
        """Update a divergence record's content and source transcript IDs.

        ``updated_at`` is automatically refreshed by the DB trigger.

        Args:
            divergence_id: Target divergence ID.
            content: New divergence description text.
            source_transcript_ids: JSON array string (≥ 2 elements).

        Returns:
            Updated row dict, or ``None`` if not found.
        """
        with self._connection_factory() as conn:
            conn.execute(
                f"UPDATE {TABLE} SET content = ?, source_transcript_ids = ? "
                "WHERE id = ?",
                (content, source_transcript_ids, divergence_id),
            )
            return self._fetch_by_id(conn, divergence_id)

    # ── get by discussion ──────────────────────────────────────

    def get_by_discussion(self, discussion_id: str) -> list[dict[str, Any]]:
        """Return all divergence records for a discussion.

        Args:
            discussion_id: Target discussion ID.

        Returns:
            List of divergence row dicts.
        """
        with self._connection_factory() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {TABLE} WHERE discussion_id = ?",
                (discussion_id,),
            )
            return [self._row_to_dict(r) for r in cursor.fetchall()]

    # ── helpers ────────────────────────────────────────────────

    def _fetch_by_id(
        self, conn: sqlite3.Connection, record_id: str
    ) -> Optional[dict[str, Any]]:
        """Fetch a divergence row using an existing connection."""
        row = conn.execute(
            f"SELECT * FROM {TABLE} WHERE id = ?", (record_id,)
        ).fetchone()
        return self._row_to_dict(row) if row else None
