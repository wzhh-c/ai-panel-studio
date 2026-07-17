"""Repository for the ``expert`` table."""

import logging
from typing import Any, Optional

import sqlite3

from app.repositories.base import BaseRepository

logger = logging.getLogger(__name__)

TABLE = "expert"

EXPERT_COLUMNS = [
    "id",
    "name",
    "role",
    "profession",
    "title",
    "stance",
    "color",
    "discussion_id",
    "created_at",
    "updated_at",
]


class ExpertRepository(BaseRepository):
    """Data access for the ``expert`` table."""

    # ── create ─────────────────────────────────────────────────

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Insert an expert and return the created row.

        Args:
            data: Column-value mapping. Must include ``id``, ``name``,
                ``role``, ``profession``, ``title``, ``stance``, ``color``,
                ``discussion_id``.

        Returns:
            The inserted row as a dict.

        Raises:
            DuplicateRecordError: A moderator already exists for this
                discussion (unique partial index).
            ForeignKeyError: ``discussion_id`` does not exist.
        """
        columns = [c for c in EXPERT_COLUMNS if c in data]
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

    # ── delete by discussion ───────────────────────────────────

    def delete_by_discussion(self, discussion_id: str) -> int:
        """Remove all experts belonging to a discussion.

        Args:
            discussion_id: Target discussion ID.

        Returns:
            Number of rows deleted.
        """
        with self._connection_factory() as conn:
            cursor = conn.execute(
                f"DELETE FROM {TABLE} WHERE discussion_id = ?", (discussion_id,)
            )
            count = cursor.rowcount
            logger.debug("Deleted %d experts for discussion %s", count, discussion_id)
            return count

    # ── get moderator ──────────────────────────────────────────

    def get_moderator(self, discussion_id: str) -> Optional[dict[str, Any]]:
        """Return the moderator for a discussion.

        Args:
            discussion_id: Target discussion ID.

        Returns:
            Moderator row dict or ``None``.
        """
        with self._connection_factory() as conn:
            row = conn.execute(
                f"SELECT * FROM {TABLE} WHERE discussion_id = ? AND role = 'moderator'",
                (discussion_id,),
            ).fetchone()
            return self._row_to_dict(row) if row else None

    # ── helpers ────────────────────────────────────────────────

    def _fetch_by_id(
        self, conn: sqlite3.Connection, record_id: str
    ) -> Optional[dict[str, Any]]:
        """Fetch an expert row using an existing connection."""
        row = conn.execute(
            f"SELECT * FROM {TABLE} WHERE id = ?", (record_id,)
        ).fetchone()
        return self._row_to_dict(row) if row else None
