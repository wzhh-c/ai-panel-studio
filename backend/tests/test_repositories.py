"""Unit tests for the repository layer.

All tests run against an in-memory SQLite database.  A single persistent
connection is shared across repository calls so that the schema and data
survive method boundaries.
"""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

import pytest

from app.exceptions import DuplicateRecordError, ForeignKeyError
from app.repositories.base import BaseRepository
from app.repositories.discussion_repository import DiscussionRepository
from app.repositories.expert_repository import ExpertRepository
from app.repositories.transcript_repository import TranscriptRepository
from app.repositories.consensus_repository import ConsensusRepository
from app.repositories.divergence_repository import DivergenceRepository


# ── helpers ───────────────────────────────────────────────────────


def _load_schema() -> str:
    """Read the DDL schema from the project docs folder."""
    schema_path = (
        Path(__file__).resolve().parent.parent / "docs" / "schema.sql"
    )
    return schema_path.read_text(encoding="utf-8")


def _make_connection_factory() -> (
    "tuple[Generator[sqlite3.Connection, None, None], sqlite3.Connection]"
):
    """Create a context-manager factory that returns the **same** in-memory
    connection on every call.  The connection is never closed while the DB
    is in use, so tables and data persist across repository method calls.
    """
    conn = sqlite3.connect(":memory:")
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

    return factory, conn


# ── fixtures ──────────────────────────────────────────────────────


@pytest.fixture(scope="function")
def connection_factory_and_conn() -> (
    "tuple[Generator[sqlite3.Connection, None, None], sqlite3.Connection]"
):
    """Provide a fresh in-memory DB per test function."""
    factory, conn = _make_connection_factory()
    yield factory, conn
    conn.close()


@pytest.fixture
def base_repo(connection_factory_and_conn) -> BaseRepository:
    factory, _ = connection_factory_and_conn
    return BaseRepository(connection_factory=factory)


@pytest.fixture
def discussion_repo(connection_factory_and_conn) -> DiscussionRepository:
    factory, _ = connection_factory_and_conn
    return DiscussionRepository(connection_factory=factory)


@pytest.fixture
def expert_repo(connection_factory_and_conn) -> ExpertRepository:
    factory, _ = connection_factory_and_conn
    return ExpertRepository(connection_factory=factory)


@pytest.fixture
def transcript_repo(connection_factory_and_conn) -> TranscriptRepository:
    factory, _ = connection_factory_and_conn
    return TranscriptRepository(connection_factory=factory)


@pytest.fixture
def consensus_repo(connection_factory_and_conn) -> ConsensusRepository:
    factory, _ = connection_factory_and_conn
    return ConsensusRepository(connection_factory=factory)


@pytest.fixture
def divergence_repo(connection_factory_and_conn) -> DivergenceRepository:
    factory, _ = connection_factory_and_conn
    return DivergenceRepository(connection_factory=factory)


@pytest.fixture
def conn(connection_factory_and_conn) -> sqlite3.Connection:
    _, conn = connection_factory_and_conn
    return conn


# ── shared seed data helpers ──────────────────────────────────────


def _seed_user(conn: sqlite3.Connection, user_id: str, name: str) -> None:
    conn.execute(
        'INSERT INTO "user" (id, name) VALUES (?, ?)', (user_id, name)
    )


def _seed_discussion(
    conn: sqlite3.Connection,
    discussion_id: str,
    topic: str,
    created_by: str,
    status: str = "GENERATING",
) -> None:
    conn.execute(
        "INSERT INTO discussion (id, topic, expert_count, status, created_by) "
        "VALUES (?, ?, 4, ?, ?)",
        (discussion_id, topic, status, created_by),
    )


def _seed_expert(
    conn: sqlite3.Connection,
    expert_id: str,
    name: str,
    discussion_id: str,
    role: str = "expert",
) -> None:
    conn.execute(
        "INSERT INTO expert (id, name, role, profession, title, stance, "
        "color, discussion_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (expert_id, name, role, "prof", "title", "stance", "#000001", discussion_id),
    )


# ═══════════════════════════════════════════════════════════════════
# BaseRepository
# ═══════════════════════════════════════════════════════════════════


class TestBaseRepository:
    """Tests for generic CRUD inherited by every repository."""

    def test_get_by_id_returns_dict(self, base_repo, conn):
        uid = str(uuid.uuid4())
        _seed_user(conn, uid, "Alice")
        row = base_repo.get_by_id(uid, "user")
        assert row is not None
        assert row["name"] == "Alice"

    def test_get_by_id_returns_none_for_missing(self, base_repo):
        assert base_repo.get_by_id("nonexistent", "user") is None

    def test_list_all_returns_paginated_rows(self, base_repo, conn):
        for i in range(3):
            _seed_user(conn, str(uuid.uuid4()), f"User{i}")
        rows = base_repo.list_all("user", limit=2, offset=0)
        assert len(rows) == 2

    def test_delete_removes_row(self, base_repo, conn):
        uid = str(uuid.uuid4())
        _seed_user(conn, uid, "Bob")
        assert base_repo.delete(uid, "user") is True
        assert base_repo.get_by_id(uid, "user") is None

    def test_delete_returns_false_when_not_found(self, base_repo):
        assert base_repo.delete("ghost", "user") is False


# ═══════════════════════════════════════════════════════════════════
# DiscussionRepository
# ═══════════════════════════════════════════════════════════════════


class TestDiscussionRepository:
    """Tests for DiscussionRepository."""

    def test_create_discussion(self, discussion_repo, conn):
        uid = str(uuid.uuid4())
        did = str(uuid.uuid4())
        _seed_user(conn, uid, "Creator")

        disc = discussion_repo.create(
            {"id": did, "topic": "AI Ethics", "created_by": uid}
        )
        assert disc["id"] == did
        assert disc["topic"] == "AI Ethics"
        assert disc["status"] == "GENERATING"

    def test_create_discussion_foreign_key_error(self, discussion_repo):
        did = str(uuid.uuid4())
        with pytest.raises(ForeignKeyError):
            discussion_repo.create(
                {"id": did, "topic": "Bad", "created_by": "no-such-user"}
            )

    def test_update_status(self, discussion_repo, conn):
        uid = str(uuid.uuid4())
        did = str(uuid.uuid4())
        _seed_user(conn, uid, "U")
        discussion_repo.create({"id": did, "topic": "T", "created_by": uid})

        updated = discussion_repo.update_status(did, "IN_PROGRESS")
        assert updated is not None
        assert updated["status"] == "IN_PROGRESS"

    def test_list_by_status(self, discussion_repo, conn):
        uid = str(uuid.uuid4())
        _seed_user(conn, uid, "U")
        for i in range(3):
            discussion_repo.create(
                {"id": str(uuid.uuid4()), "topic": f"T{i}", "created_by": uid}
            )
        # default status is GENERATING
        results = discussion_repo.list_by_status("GENERATING")
        assert len(results) == 3

    def test_get_detail_includes_related_data(self, discussion_repo, conn):
        uid = str(uuid.uuid4())
        did = str(uuid.uuid4())
        eid = str(uuid.uuid4())
        tid = str(uuid.uuid4())
        cid = str(uuid.uuid4())
        divid = str(uuid.uuid4())

        _seed_user(conn, uid, "U")
        discussion_repo.create({"id": did, "topic": "Deep", "created_by": uid})
        _seed_expert(conn, eid, "Expert1", did)
        conn.execute(
            "INSERT INTO transcript (id, sequence, content, speaker_id, "
            "discussion_id, speech_type) VALUES (?, 1, 'Hello', ?, ?, 'main')",
            (tid, eid, did),
        )
        conn.execute(
            "INSERT INTO consensus (id, content, discussion_id, "
            "source_transcript_ids) VALUES (?, 'agree', ?, ?)",
            (cid, did, json.dumps([tid, tid])),
        )
        conn.execute(
            "INSERT INTO divergence (id, content, discussion_id, sides, "
            "source_transcript_ids) VALUES (?, 'disagree', ?, ?, ?)",
            (divid, did, json.dumps([{"eid": eid, "label": "pro"}, {"eid": "x", "label": "con"}]), json.dumps([tid, tid])),
        )

        detail = discussion_repo.get_detail(did)
        assert detail is not None
        assert len(detail["experts"]) == 1
        assert len(detail["transcripts"]) == 1
        assert len(detail["consensus_list"]) == 1
        assert len(detail["divergence_list"]) == 1


# ═══════════════════════════════════════════════════════════════════
# ExpertRepository
# ═══════════════════════════════════════════════════════════════════


class TestExpertRepository:
    """Tests for ExpertRepository."""

    def _make_expert_data(self, discussion_id: str, role: str = "expert") -> dict:
        return {
            "id": str(uuid.uuid4()),
            "name": "Dr. Smith",
            "role": role,
            "profession": "Philosopher",
            "title": "Professor",
            "stance": "pro-AI",
            "color": "#3B82F6",
            "discussion_id": discussion_id,
        }

    def test_create_expert(self, expert_repo, conn):
        uid, did = str(uuid.uuid4()), str(uuid.uuid4())
        _seed_user(conn, uid, "U")
        _seed_discussion(conn, did, "T", uid)

        expert = expert_repo.create(self._make_expert_data(did))
        assert expert["name"] == "Dr. Smith"
        assert expert["role"] == "expert"

    def test_create_expert_foreign_key_error(self, expert_repo):
        with pytest.raises(ForeignKeyError):
            expert_repo.create(self._make_expert_data("bad-disc-id"))

    def test_delete_by_discussion(self, expert_repo, conn):
        uid, did = str(uuid.uuid4()), str(uuid.uuid4())
        _seed_user(conn, uid, "U")
        _seed_discussion(conn, did, "T", uid)
        expert_repo.create(self._make_expert_data(did))
        expert_repo.create(self._make_expert_data(did))

        deleted = expert_repo.delete_by_discussion(did)
        assert deleted == 2

    def test_get_moderator(self, expert_repo, conn):
        uid, did = str(uuid.uuid4()), str(uuid.uuid4())
        _seed_user(conn, uid, "U")
        _seed_discussion(conn, did, "T", uid)
        expert_repo.create(self._make_expert_data(did, role="moderator"))
        expert_repo.create(self._make_expert_data(did, role="expert"))

        mod = expert_repo.get_moderator(did)
        assert mod is not None
        assert mod["role"] == "moderator"


# ═══════════════════════════════════════════════════════════════════
# TranscriptRepository
# ═══════════════════════════════════════════════════════════════════


class TestTranscriptRepository:
    """Tests for TranscriptRepository — especially sequence generation."""

    def _make_transcript_data(
        self, discussion_id: str, speaker_id: str, content: str = "A point"
    ) -> dict[str, str]:
        return {
            "id": str(uuid.uuid4()),
            "content": content,
            "speaker_id": speaker_id,
            "discussion_id": discussion_id,
            "speech_type": "main",
        }

    def test_create_transcript(self, transcript_repo, conn):
        uid, did, eid = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        _seed_user(conn, uid, "U")
        _seed_discussion(conn, did, "T", uid)
        _seed_expert(conn, eid, "E", did)

        t = transcript_repo.create(self._make_transcript_data(did, eid))
        assert t["content"] == "A point"
        assert t["sequence"] == 1

    def test_sequence_auto_increment_three_inserts(self, transcript_repo, conn):
        """Insert 3 transcripts and verify sequences are 1, 2, 3."""
        uid, did, eid = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        _seed_user(conn, uid, "U")
        _seed_discussion(conn, did, "T", uid)
        _seed_expert(conn, eid, "E", did)

        t1 = transcript_repo.create(self._make_transcript_data(did, eid, "First"))
        t2 = transcript_repo.create(self._make_transcript_data(did, eid, "Second"))
        t3 = transcript_repo.create(self._make_transcript_data(did, eid, "Third"))

        assert t1["sequence"] == 1
        assert t2["sequence"] == 2
        assert t3["sequence"] == 3

    def test_list_by_discussion_ordered_by_sequence(self, transcript_repo, conn):
        uid, did, eid = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        _seed_user(conn, uid, "U")
        _seed_discussion(conn, did, "T", uid)
        _seed_expert(conn, eid, "E", did)

        transcript_repo.create(self._make_transcript_data(did, eid, "C"))
        transcript_repo.create(self._make_transcript_data(did, eid, "A"))
        transcript_repo.create(self._make_transcript_data(did, eid, "B"))

        rows = transcript_repo.list_by_discussion(did)
        assert len(rows) == 3
        assert [r["sequence"] for r in rows] == [1, 2, 3]

    def test_get_replies(self, transcript_repo, conn):
        uid, did, eid = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        _seed_user(conn, uid, "U")
        _seed_discussion(conn, did, "T", uid)
        _seed_expert(conn, eid, "E", did)

        parent = transcript_repo.create(self._make_transcript_data(did, eid, "Q"))
        reply_data = self._make_transcript_data(did, eid, "R")

        # Manually insert reply with reply_to_id so we control the columns
        conn.execute(
            "INSERT INTO transcript (id, sequence, content, speaker_id, "
            "discussion_id, speech_type, reply_to_id) "
            "VALUES (?, 2, ?, ?, ?, 'supplement', ?)",
            (reply_data["id"], "R", eid, did, parent["id"]),
        )

        replies = transcript_repo.get_replies(parent["id"])
        assert len(replies) == 1
        assert replies[0]["content"] == "R"


# ═══════════════════════════════════════════════════════════════════
# ConsensusRepository
# ═══════════════════════════════════════════════════════════════════


class TestConsensusRepository:
    """Tests for ConsensusRepository."""

    def _make_consensus_data(self, discussion_id: str) -> dict[str, Any]:
        return {
            "id": str(uuid.uuid4()),
            "content": "We agree on X",
            "discussion_id": discussion_id,
            "source_transcript_ids": json.dumps(["t1", "t2"]),
        }

    def test_create_consensus(self, consensus_repo, conn):
        uid, did = str(uuid.uuid4()), str(uuid.uuid4())
        _seed_user(conn, uid, "U")
        _seed_discussion(conn, did, "T", uid)

        c = consensus_repo.create(self._make_consensus_data(did))
        assert c["content"] == "We agree on X"

    def test_update_consensus(self, consensus_repo, conn):
        uid, did = str(uuid.uuid4()), str(uuid.uuid4())
        _seed_user(conn, uid, "U")
        _seed_discussion(conn, did, "T", uid)

        c = consensus_repo.create(self._make_consensus_data(did))
        updated = consensus_repo.update(
            c["id"], "Revised consensus", json.dumps(["t1", "t3"])
        )
        assert updated is not None
        assert updated["content"] == "Revised consensus"
        assert json.loads(updated["source_transcript_ids"]) == ["t1", "t3"]

    def test_get_by_discussion(self, consensus_repo, conn):
        uid, did = str(uuid.uuid4()), str(uuid.uuid4())
        _seed_user(conn, uid, "U")
        _seed_discussion(conn, did, "T", uid)

        consensus_repo.create(self._make_consensus_data(did))
        consensus_repo.create(self._make_consensus_data(did))

        items = consensus_repo.get_by_discussion(did)
        assert len(items) == 2


# ═══════════════════════════════════════════════════════════════════
# DivergenceRepository
# ═══════════════════════════════════════════════════════════════════


class TestDivergenceRepository:
    """Tests for DivergenceRepository."""

    def _make_divergence_data(self, discussion_id: str) -> dict[str, Any]:
        return {
            "id": str(uuid.uuid4()),
            "content": "We disagree on Y",
            "discussion_id": discussion_id,
            "sides": json.dumps(
                [{"expert_id": "a", "stance_label": "pro"}, {"expert_id": "b", "stance_label": "con"}]
            ),
            "source_transcript_ids": json.dumps(["t1", "t2"]),
        }

    def test_create_divergence(self, divergence_repo, conn):
        uid, did = str(uuid.uuid4()), str(uuid.uuid4())
        _seed_user(conn, uid, "U")
        _seed_discussion(conn, did, "T", uid)

        d = divergence_repo.create(self._make_divergence_data(did))
        assert d["content"] == "We disagree on Y"

    def test_update_divergence(self, divergence_repo, conn):
        uid, did = str(uuid.uuid4()), str(uuid.uuid4())
        _seed_user(conn, uid, "U")
        _seed_discussion(conn, did, "T", uid)

        d = divergence_repo.create(self._make_divergence_data(did))
        updated = divergence_repo.update(
            d["id"], "Revised divergence", json.dumps(["t1", "t3"])
        )
        assert updated is not None
        assert updated["content"] == "Revised divergence"
        assert json.loads(updated["source_transcript_ids"]) == ["t1", "t3"]

    def test_get_by_discussion(self, divergence_repo, conn):
        uid, did = str(uuid.uuid4()), str(uuid.uuid4())
        _seed_user(conn, uid, "U")
        _seed_discussion(conn, did, "T", uid)

        divergence_repo.create(self._make_divergence_data(did))
        divergence_repo.create(self._make_divergence_data(did))

        items = divergence_repo.get_by_discussion(did)
        assert len(items) == 2
