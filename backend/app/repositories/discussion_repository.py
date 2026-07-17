"""Repository for the ``discussion`` table."""

import logging
from typing import Any, Optional

import sqlite3

from app.repositories.base import BaseRepository

logger = logging.getLogger(__name__)

TABLE = "discussion"

DISCUSSION_COLUMNS = [
    "id",
    "topic",
    "expert_count",
    "status",
    "summary",
    "started_at",
    "ended_at",
    "created_by",
    "created_at",
    "updated_at",
]


class DiscussionRepository(BaseRepository):
    """Data access for the ``discussion`` table."""

    # ── create ─────────────────────────────────────────────────

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Insert a new discussion and return the created row.

        Args:
            data: Column-value mapping. Must include ``id``, ``topic``,
                ``created_by``.

        Returns:
            The inserted row as a dict.

        Raises:
            ForeignKeyError: ``created_by`` does not reference a valid user.
        """
        columns = [c for c in DISCUSSION_COLUMNS if c in data]
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

    # ── update status ──────────────────────────────────────────

    def update_status(self, discussion_id: str, new_status: str) -> Optional[dict[str, Any]]:
        """Transition a discussion to a new lifecycle status.

        Args:
            discussion_id: Target discussion ID.
            new_status: One of GENERATING / PENDING_CONFIRM /
                IN_PROGRESS / COMPLETED.

        Returns:
            Updated row dict, or ``None`` if the discussion was not found.
        """
        with self._connection_factory() as conn:
            conn.execute(
                f"UPDATE {TABLE} SET status = ? WHERE id = ?",
                (new_status, discussion_id),
            )
            return self._fetch_by_id(conn, discussion_id)

    # ── list by status ─────────────────────────────────────────

    def list_by_status(
        self, status: str, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Return discussions filtered by lifecycle status.

        Args:
            status: Lifecycle status to filter on.
            limit: Max rows.
            offset: Rows to skip.

        Returns:
            List of row dicts.
        """
        with self._connection_factory() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {TABLE} WHERE status = ? LIMIT ? OFFSET ?",
                (status, limit, offset),
            )
            return [self._row_to_dict(r) for r in cursor.fetchall()]

    # ── get detail (JOIN) ──────────────────────────────────────

    def get_detail(self, discussion_id: str) -> Optional[dict[str, Any]]:
        """Return a discussion with its experts, transcripts, consensus
        records, and divergences in a single aggregate dict.

        Transcripts are ordered by ``sequence`` ascending.

        Args:
            discussion_id: Target discussion ID.

        Returns:
            Nested dict or ``None`` if the discussion does not exist.
        """
        with self._connection_factory() as conn:
            disc = self._fetch_by_id(conn, discussion_id)
            if disc is None:
                return None

            experts = [
                self._row_to_dict(r)
                for r in conn.execute(
                    "SELECT * FROM expert WHERE discussion_id = ? ORDER BY role",
                    (discussion_id,),
                ).fetchall()
            ]

            transcripts = [
                self._row_to_dict(r)
                for r in conn.execute(
                    "SELECT * FROM transcript WHERE discussion_id = ? "
                    "ORDER BY sequence ASC",
                    (discussion_id,),
                ).fetchall()
            ]

            consensus_list = [
                self._row_to_dict(r)
                for r in conn.execute(
                    "SELECT * FROM consensus WHERE discussion_id = ?",
                    (discussion_id,),
                ).fetchall()
            ]

            divergence_list = [
                self._row_to_dict(r)
                for r in conn.execute(
                    "SELECT * FROM divergence WHERE discussion_id = ?",
                    (discussion_id,),
                ).fetchall()
            ]

            disc["experts"] = experts
            disc["transcripts"] = transcripts
            disc["consensus_list"] = consensus_list
            disc["divergence_list"] = divergence_list
            return disc

    # ── helpers ────────────────────────────────────────────────

    def _fetch_by_id(
        self, conn: sqlite3.Connection, record_id: str
    ) -> Optional[dict[str, Any]]:
        """Fetch a discussion row using an existing connection."""
        row = conn.execute(
            f"SELECT * FROM {TABLE} WHERE id = ?", (record_id,)
        ).fetchone()
        return self._row_to_dict(row) if row else None
