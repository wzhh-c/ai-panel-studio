# -*- coding: utf-8 -*-
"""Unit tests for SessionManager and SpeakerEngine.

All tests use an in-memory SQLite database and mocked LLM calls.
"""

import asyncio
import json
import uuid
from typing import Any, Generator

import pytest
import sqlite3

from app.llm.client import DeepSeekClient
from app.repositories.consensus_repository import ConsensusRepository
from app.repositories.divergence_repository import DivergenceRepository
from app.repositories.expert_repository import ExpertRepository
from app.repositories.discussion_repository import DiscussionRepository
from app.repositories.transcript_repository import TranscriptRepository
from app.services.session_manager import DiscussionSession, SessionManager
from app.services.speaker_engine import SpeakerEngine


# ── fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def repos(in_memory_db):
    """Provide fresh repository instances backed by an in-memory DB."""
    factory, conn = in_memory_db
    repos_dict = {
        "discussion": DiscussionRepository(connection_factory=factory),
        "expert": ExpertRepository(connection_factory=factory),
        "transcript": TranscriptRepository(connection_factory=factory),
        "consensus": ConsensusRepository(connection_factory=factory),
        "divergence": DivergenceRepository(connection_factory=factory),
    }
    yield repos_dict


@pytest.fixture
def llm_client():
    """Mock DeepSeek client (env var set in conftest)."""
    return DeepSeekClient()


@pytest.fixture
def session_mgr():
    """Fresh in-memory SessionManager."""
    return SessionManager()


# ── seed helpers ──────────────────────────────────────────────────


def _seed_user(conn: sqlite3.Connection, user_id: str, name: str = "TestU") -> None:
    conn.execute(
        'INSERT INTO "user" (id, name) VALUES (?, ?)', (user_id, name)
    )
    conn.commit()


def _seed_discussion(
    conn: sqlite3.Connection, did: str, topic: str, uid: str, status: str = "GENERATING"
) -> None:
    conn.execute(
        "INSERT INTO discussion (id, topic, expert_count, status, created_by) "
        "VALUES (?, ?, 4, ?, ?)",
        (did, topic, status, uid),
    )
    conn.commit()


def _seed_expert(conn: sqlite3.Connection, eid: str, name: str, did: str, role: str = "expert") -> None:
    conn.execute(
        "INSERT INTO expert (id, name, role, profession, title, stance, color, discussion_id) "
        "VALUES (?, ?, ?, 'TestProf', 'Dr.', 'neutral', '#000001', ?)",
        (eid, name, role, did),
    )
    conn.commit()


# ═══════════════════════════════════════════════════════════════════
# SessionManager tests
# ═══════════════════════════════════════════════════════════════════


class TestSessionManager:
    """Tests for DiscussionSession and SessionManager."""

    def test_create_and_get_session(self, session_mgr):
        experts = [{"id": "e1", "name": "Mod", "role": "moderator"}]
        session_mgr.create_session("d1", experts)
        sess = session_mgr.get_session("d1")
        assert sess is not None
        assert sess.discussion_id == "d1"
        assert sess.status == "PENDING_CONFIRM"

    def test_get_session_returns_none_for_unknown(self, session_mgr):
        assert session_mgr.get_session("nonexistent") is None

    def test_remove_session(self, session_mgr):
        session_mgr.create_session("d1", [])
        session_mgr.remove_session("d1")
        assert session_mgr.get_session("d1") is None

    @pytest.mark.asyncio
    async def test_enqueue_event(self, session_mgr):
        session_mgr.create_session("d1", [])
        await session_mgr.enqueue_event("d1", "speech", {"text": "hello"})
        sess = session_mgr.get_session("d1")
        assert sess is not None
        assert not sess.transcript_queue.empty()

    @pytest.mark.asyncio
    async def test_stop_session_sets_event(self, session_mgr):
        session_mgr.create_session("d1", [])
        await session_mgr.stop_session("d1")
        sess = session_mgr.get_session("d1")
        assert sess is not None
        assert sess.stop_event.is_set()

    @pytest.mark.asyncio
    async def test_concurrent_session_isolation(self, session_mgr):
        """Events from one discussion do NOT leak into another."""
        session_mgr.create_session("d1", [])
        session_mgr.create_session("d2", [])

        await session_mgr.enqueue_event("d1", "speech", {"t": 1})
        await session_mgr.enqueue_event("d2", "speech", {"t": 2})

        q1 = session_mgr.get_session("d1").transcript_queue
        q2 = session_mgr.get_session("d2").transcript_queue

        assert q1.qsize() == 1
        assert q2.qsize() == 1

        e1 = await q1.get()
        e2 = await q2.get()

        assert e1["data"]["t"] == 1
        assert e2["data"]["t"] == 2


# ═══════════════════════════════════════════════════════════════════
# SpeakerEngine tests
# ═══════════════════════════════════════════════════════════════════


class TestSpeakerEngine:
    """Tests for SpeakerEngine with mock LLM."""

    @pytest.mark.asyncio
    async def test_start_discussion_creates_speech_loop(self, repos, llm_client, session_mgr):
        """Starting a discussion should enqueue at least the moderator opening."""
        uid, did = str(uuid.uuid4()), str(uuid.uuid4())
        mod_id = str(uuid.uuid4())

        factories = [v._connection_factory for v in repos.values() if hasattr(v, '_connection_factory')]

        # Use the transcript repo's factory to seed.
        repo = repos["transcript"]
        conn = repo._connection_factory()
        # Need to seed through the context manager.
        with repo._connection_factory() as c:
            _seed_user(c, uid)
            _seed_discussion(c, did, "Test Topic", uid)
            _seed_expert(c, mod_id, "Moderator", did, "moderator")
            _seed_expert(c, str(uuid.uuid4()), "Expert1", did, "expert")
            _seed_expert(c, str(uuid.uuid4()), "Expert2", did, "expert")

        experts = [
            {"id": mod_id, "name": "Moderator", "role": "moderator", "profession": "Host",
             "title": "Mr.", "stance": "neutral", "color": "#111111"},
        ]
        # Add the actual seeded experts.
        for eid, ename in [("e2", "Expert1"), ("e3", "Expert2")]:
            experts.append(
                {"id": eid, "name": ename, "role": "expert", "profession": "P",
                 "title": "Dr.", "stance": "balanced", "color": "#222222"}
            )

        session_mgr.create_session(did, experts)
        engine = SpeakerEngine(
            llm_client=llm_client,
            transcript_repo=repos["transcript"],
            consensus_repo=repos["consensus"],
            divergence_repo=repos["divergence"],
            sm=session_mgr,
        )

        await engine.start_discussion(did)
        # Wait for moderator opening to be enqueued.
        await asyncio.sleep(0.5)

        sess = session_mgr.get_session(did)
        assert sess is not None
        assert sess.running is True

        # at least the moderator opening speech should be in the queue
        assert not sess.transcript_queue.empty()

        # Stop the loop.
        await session_mgr.stop_session(did)
        await asyncio.sleep(1.5)

    @pytest.mark.asyncio
    async def test_end_discussion_generates_summary(self, repos, llm_client, session_mgr):
        """Ending a discussion should produce a summary event in the queue."""
        uid, did = str(uuid.uuid4()), str(uuid.uuid4())
        mod_id = str(uuid.uuid4())

        with repos["transcript"]._connection_factory() as c:
            _seed_user(c, uid)
            _seed_discussion(c, did, "AI Ethics", uid)
            _seed_expert(c, mod_id, "Moderator", did, "moderator")
            _seed_expert(c, str(uuid.uuid4()), "ExpertA", did, "expert")

        experts = [
            {"id": mod_id, "name": "Moderator", "role": "moderator"},
        ]

        session_mgr.create_session(did, experts)
        engine = SpeakerEngine(
            llm_client=llm_client,
            transcript_repo=repos["transcript"],
            consensus_repo=repos["consensus"],
            divergence_repo=repos["divergence"],
            sm=session_mgr,
        )

        # Start, then immediately end.
        await engine.start_discussion(did)
        await asyncio.sleep(0.3)

        result = await engine.end_discussion(did)
        await asyncio.sleep(0.3)

        assert result is not None
        assert "summary" in result
        assert len(result["summary"]) > 0

    @pytest.mark.asyncio
    async def test_roster_regeneration_flow(self, repos, llm_client):
        """Regenerate roster: delete old experts, create new ones."""
        uid, did = str(uuid.uuid4()), str(uuid.uuid4())
        old_eid = str(uuid.uuid4())

        with repos["transcript"]._connection_factory() as c:
            _seed_user(c, uid)
            _seed_discussion(c, did, "AI Ethics", uid, "PENDING_CONFIRM")
            _seed_expert(c, old_eid, "Old Expert", did, "expert")

        # Simulate regenerating.
        repos["expert"].delete_by_discussion(did)

        roster = await llm_client.generate_roster("AI Ethics", 2)
        moderator = roster["moderator"]
        experts = roster["experts"]

        repos["expert"].create({
            "id": moderator.get("id", str(uuid.uuid4())),
            "name": moderator["name"],
            "role": "moderator",
            "profession": moderator.get("profession", ""),
            "title": moderator.get("title", ""),
            "stance": moderator.get("stance", ""),
            "color": moderator.get("color", "#111"),
            "discussion_id": did,
        })
        for e in experts:
            repos["expert"].create({
                "id": e.get("id", str(uuid.uuid4())),
                "name": e["name"],
                "role": "expert",
                "profession": e.get("profession", ""),
                "title": e.get("title", ""),
                "stance": e.get("stance", ""),
                "color": e.get("color", "#222"),
                "discussion_id": did,
            })

        # Verify old expert is gone and new ones exist.
        mod = repos["expert"].get_moderator(did)
        assert mod is not None

        # Check all experts for this discussion (moderator + 2 experts).
        detail = repos["discussion"].get_detail(did)
        assert detail is not None
        assert len(detail["experts"]) == 3  # 1 mod + 2 experts
