# -*- coding: utf-8 -*-
"""In-memory session manager for parallel discussion SSE streams.

Each discussion gets its own ``DiscussionSession`` with an ``asyncio.Queue``
for pushing real-time events to connected SSE clients.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DiscussionSession:
    """Holds the runtime state of one discussion."""

    def __init__(self, discussion_id: str, experts: list[dict[str, Any]]) -> None:
        self.discussion_id: str = discussion_id
        self.status: str = "PENDING_CONFIRM"
        self.experts: list[dict[str, Any]] = experts
        self.transcript_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.running: bool = False
        self.stop_event: asyncio.Event = asyncio.Event()


class SessionManager:
    """Manages in-memory ``DiscussionSession`` instances.

    Sessions are stored in a plain dict keyed by ``discussion_id``.
    This manager is **not** thread-safe — it is designed for a single-process
    async server.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, DiscussionSession] = {}

    # ── session lifecycle ───────────────────────────────────────

    def create_session(
        self, discussion_id: str, experts: list[dict[str, Any]]
    ) -> DiscussionSession:
        """Create and store a new session.

        Args:
            discussion_id: Target discussion ID.
            experts: Full roster (moderator first).

        Returns:
            The newly created ``DiscussionSession``.
        """
        session = DiscussionSession(discussion_id, experts)
        self._sessions[discussion_id] = session
        logger.info("Session created for discussion %s", discussion_id)
        return session

    def get_session(self, discussion_id: str) -> Optional[DiscussionSession]:
        """Return the session for *discussion_id*, or ``None``."""
        return self._sessions.get(discussion_id)

    def remove_session(self, discussion_id: str) -> None:
        """Remove a session from memory."""
        self._sessions.pop(discussion_id, None)
        logger.info("Session removed for discussion %s", discussion_id)

    # ── event helpers ───────────────────────────────────────────

    @staticmethod
    def _build_envelope(
        event_type: str, discussion_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Wrap payload in the standard SSE envelope."""
        return {
            "event": event_type,
            "discussion_id": discussion_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }

    async def enqueue_event(
        self, discussion_id: str, event_type: str, data: dict[str, Any]
    ) -> None:
        """Push an event into the discussion's queue for SSE consumers.

        Args:
            discussion_id: Target discussion.
            event_type: One of ``speech``, ``status_update``,
                ``consensus_update``, ``divergence_update``, ``summary``.
            data: Event payload (without envelope).
        """
        session = self._sessions.get(discussion_id)
        if session is None:
            logger.warning(
                "enqueue_event called for unknown discussion %s", discussion_id
            )
            return
        envelope = self._build_envelope(event_type, discussion_id, data)
        await session.transcript_queue.put(envelope)
        logger.debug(
            "Event %s enqueued for discussion %s", event_type, discussion_id
        )

    async def stop_session(self, discussion_id: str) -> None:
        """Signal the speaker loop to stop gracefully.

        Args:
            discussion_id: Target discussion.
        """
        session = self._sessions.get(discussion_id)
        if session is None:
            return
        session.stop_event.set()
        logger.info("Stop signal sent for discussion %s", discussion_id)


# ── module-level singleton ─────────────────────────────────────

session_manager = SessionManager()
