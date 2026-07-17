"""Repository for the ``transcript`` table.

The ``create`` method implements atomic sequence generation: it computes
``MAX(sequence) + 1`` for the target discussion inside an explicit transaction
to guarantee monotonic, gap-free ordering.
"""

import logging
from typing import Any, Optional

import sqlite3

from app.repositories.base import BaseRepository

logger = logging.getLogger(__name__)

TABLE = "transcript"

TRANSCRIPT_COLUMNS = [
    "id",
    "sequence",
    "content",
    "speaker_id",
    "discussion_id",
    "speech_type",
    "reply_to_id",
    "created_at",
    "updated_at",
]


class TranscriptRepository(BaseRepository):
    """Data access for the ``transcript`` table."""

    # ── create (with atomic sequence) ──────────────────────────

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Insert a transcript row, auto-generating ``sequence``.

        Sequence is computed as ``MAX(sequence) + 1`` within the target
        discussion. The lookup and insert run inside an explicit SQLite
        transaction to prevent races.

        Args:
            data: Column-value mapping. ``sequence`` is **ignored** —
                the repository always computes it. Must include ``id``,
                ``content``, ``speaker_id``, ``discussion_id``.

        Returns:
            The inserted row as a dict.

        Raises:
            ForeignKeyError: ``speaker_id``, ``discussion_id``, or
                ``reply_to_id`` is invalid.
            DuplicateRecordError: ``id`` already exists.
        """
        columns = [c for c in TRANSCRIPT_COLUMNS if c in data and c != "sequence"]
        col_names = ", ".join(['"sequence"'] + [f'"{c}"' for c in columns])
        placeholders = ", ".join(["?" for _ in range(len(columns) + 1)])

        with self._connection_factory() as conn:
            # Use SAVEPOINT so we can nest safely inside an existing
            # transaction (e.g. during tests with a shared connection).
            conn.execute("SAVEPOINT seq_insert")
            try:
                max_seq = conn.execute(
                    f"SELECT COALESCE(MAX(sequence), 0) FROM {TABLE} "
                    "WHERE discussion_id = ?",
                    (data["discussion_id"],),
                ).fetchone()[0]

                new_sequence = max_seq + 1
                values = [new_sequence] + [data[c] for c in columns]

                conn.execute(
                    f"INSERT INTO {TABLE} ({col_names}) VALUES ({placeholders})",
                    values,
                )
                conn.execute("RELEASE seq_insert")
            except sqlite3.IntegrityError as exc:
                conn.execute("ROLLBACK TO seq_insert")
                self._handle_integrity_error(exc)
                raise
            except Exception:
                conn.execute("ROLLBACK TO seq_insert")
                raise

            logger.debug(
                "Transcript %s inserted with sequence %d", data["id"], new_sequence
            )
            return self._fetch_by_id(conn, data["id"])

    # ── list by discussion ─────────────────────────────────────

    def list_by_discussion(
        self, discussion_id: str, limit: int = 500, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Return transcripts for a discussion, ordered by sequence.

        Args:
            discussion_id: Target discussion ID.
            limit: Max rows.
            offset: Rows to skip.

        Returns:
            List of row dicts, sorted by ``sequence ASC``.
        """
        with self._connection_factory() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {TABLE} WHERE discussion_id = ? "
                "ORDER BY sequence ASC LIMIT ? OFFSET ?",
                (discussion_id, limit, offset),
            )
            return [self._row_to_dict(r) for r in cursor.fetchall()]

    # ── get replies ────────────────────────────────────────────

    def get_replies(self, transcript_id: str) -> list[dict[str, Any]]:
        """Return all replies to a given transcript.

        Args:
            transcript_id: The parent transcript ID.

        Returns:
            List of reply row dicts.
        """
        with self._connection_factory() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {TABLE} WHERE reply_to_id = ? "
                "ORDER BY sequence ASC",
                (transcript_id,),
            )
            return [self._row_to_dict(r) for r in cursor.fetchall()]

    # ── helpers ────────────────────────────────────────────────

    def _fetch_by_id(
        self, conn: sqlite3.Connection, record_id: str
    ) -> Optional[dict[str, Any]]:
        """Fetch a transcript row using an existing connection."""
        row = conn.execute(
            f"SELECT * FROM {TABLE} WHERE id = ?", (record_id,)
        ).fetchone()
        return self._row_to_dict(row) if row else None
