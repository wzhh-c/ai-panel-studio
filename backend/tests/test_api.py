# -*- coding: utf-8 -*-
"""Integration tests for the Discussion REST API.

Uses an in-memory SQLite database (``check_same_thread=False`` so the
TestClient worker thread can share the connection) and the mock LLM client.
"""

import json
import uuid
from typing import Any, Generator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.consensus_repository import ConsensusRepository
from app.repositories.discussion_repository import DiscussionRepository
from app.repositories.divergence_repository import DivergenceRepository
from app.repositories.expert_repository import ExpertRepository
from app.repositories.transcript_repository import TranscriptRepository
from app.services.session_manager import SessionManager
from app.services.speaker_engine import SpeakerEngine
from app.llm.client import DeepSeekClient


# ── fixture: patch router singletons ──────────────────────────────


@pytest.fixture(autouse=True)
def _patch_router(in_memory_db, seed_user, monkeypatch):
    """Replace router-level singletons with in-memory test instances."""
    factory, _ = in_memory_db

    disc_repo = DiscussionRepository(connection_factory=factory)
    expert_repo = ExpertRepository(connection_factory=factory)
    transcript_repo = TranscriptRepository(connection_factory=factory)
    consensus_repo = ConsensusRepository(connection_factory=factory)
    divergence_repo = DivergenceRepository(connection_factory=factory)

    llm = DeepSeekClient()
    sm = SessionManager()
    engine = SpeakerEngine(
        llm_client=llm,
        transcript_repo=transcript_repo,
        consensus_repo=consensus_repo,
        divergence_repo=divergence_repo,
        sm=sm,
    )

    import app.routers.discussion as router_mod

    monkeypatch.setattr(router_mod, "_disc_repo", disc_repo)
    monkeypatch.setattr(router_mod, "_expert_repo", expert_repo)
    monkeypatch.setattr(router_mod, "_transcript_repo", transcript_repo)
    monkeypatch.setattr(router_mod, "_consensus_repo", consensus_repo)
    monkeypatch.setattr(router_mod, "_divergence_repo", divergence_repo)
    monkeypatch.setattr(router_mod, "_llm_client", llm)
    monkeypatch.setattr(router_mod, "session_manager", sm)
    monkeypatch.setattr(router_mod, "_speaker_engine", engine)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as tc:
        yield tc


# ═══════════════════════════════════════════════════════════════════
# POST /api/discussions
# ═══════════════════════════════════════════════════════════════════


class TestCreateDiscussion:

    def test_create_returns_roster_with_moderator_first(self, client):
        resp = client.post(
            "/api/discussions",
            json={
                "topic": "AI Ethics",
                "expert_count": 2,
                "user_id": "550e8400-e29b-41d4-a716-446655440001",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "PENDING_CONFIRM"
        assert "discussion_id" in body
        assert len(body["roster"]) >= 3
        assert body["roster"][0]["role"] == "moderator"

    def test_missing_topic_returns_400(self, client):
        resp = client.post("/api/discussions", json={})
        assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════
# GET /api/discussions
# ═══════════════════════════════════════════════════════════════════


class TestListDiscussions:

    def test_list_returns_items(self, client):
        client.post(
            "/api/discussions",
            json={
                "topic": "Space Ethics",
                "expert_count": 1,
                "user_id": "550e8400-e29b-41d4-a716-446655440001",
            },
        )
        resp = client.get("/api/discussions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        assert "items" in body

    def test_filter_by_status_returns_empty_for_completed(self, client):
        resp = client.get("/api/discussions?status=COMPLETED")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


# ═══════════════════════════════════════════════════════════════════
# GET /api/discussions/{id}
# ═══════════════════════════════════════════════════════════════════


class TestGetDiscussion:

    def test_detail_includes_experts(self, client):
        create = client.post(
            "/api/discussions",
            json={
                "topic": "Detail Test",
                "expert_count": 1,
                "user_id": "550e8400-e29b-41d4-a716-446655440001",
            },
        )
        did = create.json()["discussion_id"]

        resp = client.get(f"/api/discussions/{did}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["topic"] == "Detail Test"
        assert "experts" in body
        assert "transcripts" in body

    def test_nonexistent_returns_404(self, client):
        resp = client.get("/api/discussions/nonexistent")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# POST /api/discussions/{id}/start
# ═══════════════════════════════════════════════════════════════════


class TestStartDiscussion:

    def test_start_transitions_to_in_progress(self, client):
        create = client.post(
            "/api/discussions",
            json={
                "topic": "Start Test",
                "expert_count": 1,
                "user_id": "550e8400-e29b-41d4-a716-446655440001",
            },
        )
        did = create.json()["discussion_id"]

        resp = client.post(f"/api/discussions/{did}/start")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "IN_PROGRESS"
        assert "started_at" in body

    def test_cannot_start_twice(self, client):
        create = client.post(
            "/api/discussions",
            json={
                "topic": "Double Start",
                "expert_count": 1,
                "user_id": "550e8400-e29b-41d4-a716-446655440001",
            },
        )
        did = create.json()["discussion_id"]
        client.post(f"/api/discussions/{did}/start")
        resp = client.post(f"/api/discussions/{did}/start")
        assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════
# POST /api/discussions/{id}/end
# ═══════════════════════════════════════════════════════════════════


class TestEndDiscussion:

    def test_end_produces_plain_text_summary(self, client):
        create = client.post(
            "/api/discussions",
            json={
                "topic": "End Test",
                "expert_count": 1,
                "user_id": "550e8400-e29b-41d4-a716-446655440001",
            },
        )
        did = create.json()["discussion_id"]
        client.post(f"/api/discussions/{did}/start")

        # Let speaker loop run briefly to produce at least one speech.
        import time
        time.sleep(0.3)

        resp = client.post(f"/api/discussions/{did}/end")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "COMPLETED"
        assert len(body["summary"]) > 0

    def test_cannot_end_before_start(self, client):
        create = client.post(
            "/api/discussions",
            json={
                "topic": "Not Started",
                "expert_count": 1,
                "user_id": "550e8400-e29b-41d4-a716-446655440001",
            },
        )
        did = create.json()["discussion_id"]
        resp = client.post(f"/api/discussions/{did}/end")
        assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════
# POST /api/discussions/{id}/regenerate-roster
# ═══════════════════════════════════════════════════════════════════


class TestRegenerateRoster:

    def test_regenerate_preserves_status_and_moderator_first(self, client):
        create = client.post(
            "/api/discussions",
            json={
                "topic": "Regen Test",
                "expert_count": 2,
                "user_id": "550e8400-e29b-41d4-a716-446655440001",
            },
        )
        did = create.json()["discussion_id"]

        resp = client.post(f"/api/discussions/{did}/regenerate-roster")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "PENDING_CONFIRM"
        assert body["roster"][0]["role"] == "moderator"


# ═══════════════════════════════════════════════════════════════════
# GET /api/discussions/{id}/stream (SSE)
# ═══════════════════════════════════════════════════════════════════


class TestSSEStream:

    @pytest.mark.skip(reason="SSE streaming blocks TestClient; verify manually with curl")
    def test_sse_stream_structure(self, client):
        """Placeholder — SSE tested manually due to TestClient limitations."""
        pass
