# -*- coding: utf-8 -*-
"""Discussion REST API — full lifecycle management and SSE streaming.

Endpoint summary
----------------
POST   /api/discussions                          — create discussion + generate roster
GET    /api/discussions                          — list discussions
GET    /api/discussions/{discussion_id}           — discussion detail
POST   /api/discussions/{discussion_id}/start      — start discussion (SSE loop)
POST   /api/discussions/{discussion_id}/end        — end discussion + summary
POST   /api/discussions/{discussion_id}/regenerate-roster — re-generate expert roster
GET    /api/discussions/{discussion_id}/stream     — SSE event stream
"""

import asyncio
import json
import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.llm.client import DeepSeekClient
from app.repositories.consensus_repository import ConsensusRepository
from app.repositories.discussion_repository import DiscussionRepository
from app.repositories.divergence_repository import DivergenceRepository
from app.repositories.expert_repository import ExpertRepository
from app.repositories.transcript_repository import TranscriptRepository
from app.services.session_manager import session_manager
from app.services.speaker_engine import SpeakerEngine

logger = logging.getLogger(__name__)

discussion_router = APIRouter(prefix="/discussions", tags=["Discussion"])

# ── repositories (stateless — safe as module-level singletons) ─
_disc_repo = DiscussionRepository()
_expert_repo = ExpertRepository()
_transcript_repo = TranscriptRepository()
_consensus_repo = ConsensusRepository()
_divergence_repo = DivergenceRepository()

# ── LLM client ──────────────────────────────────────────────────
_llm_client = DeepSeekClient()

# ── speaker engine ──────────────────────────────────────────────
_speaker_engine = SpeakerEngine(
    llm_client=_llm_client,
    transcript_repo=_transcript_repo,
    consensus_repo=_consensus_repo,
    divergence_repo=_divergence_repo,
    sm=session_manager,
)


# ═══════════════════════════════════════════════════════════════════
# POST /discussions — create discussion
# ═══════════════════════════════════════════════════════════════════


@discussion_router.post("", status_code=201)
async def create_discussion(payload: dict[str, Any]) -> dict[str, Any]:
    """Create a discussion, generate an expert roster, and return it.

    **Flow**
    1. Create a discussion record (status=GENERATING).
    2. Call LLM to generate 1 moderator + N experts.
    3. Persist all expert rows.
    4. Transition status to PENDING_CONFIRM.
    5. Return the discussion_id and full roster.
    """
    topic: str = payload.get("topic", "").strip()
    if not topic:
        raise HTTPException(status_code=400, detail="topic is required")
    expert_count: int = payload.get("expert_count", 4)
    user_id: str = payload.get("user_id", "550e8400-e29b-41d4-a716-446655440001")

    discussion_id = str(uuid.uuid4())

    # 1. Create discussion record.
    disc_data: dict[str, Any] = {
        "id": discussion_id,
        "topic": topic,
        "expert_count": expert_count,
        "status": "GENERATING",
        "created_by": user_id,
    }
    _disc_repo.create(disc_data)

    # 2. Generate roster via LLM.
    try:
        roster_result = await _llm_client.generate_roster(topic, expert_count)
    except Exception as exc:
        logger.exception("Failed to generate roster for discussion %s", discussion_id)
        raise HTTPException(
            status_code=500,
            detail=f"LLM roster generation failed: {exc}",
        )

    moderator = roster_result["moderator"]
    experts = roster_result.get("experts", [])

    # 3. Persist experts and transition to PENDING_CONFIRM.
    #    Wrap in try/except so that any failure here triggers a full
    #    rollback, preventing orphaned GENERATING discussions.
    try:
        _expert_repo.create(
            {
                "id": moderator.get("id", str(uuid.uuid4())),
                "name": moderator["name"],
                "role": "moderator",
                "profession": moderator.get("profession", ""),
                "title": moderator.get("title", ""),
                "stance": moderator.get("stance", ""),
                "color": moderator.get("color", "#6B7280"),
                "discussion_id": discussion_id,
            }
        )

        for expert in experts:
            _expert_repo.create(
                {
                    "id": expert.get("id", str(uuid.uuid4())),
                    "name": expert["name"],
                    "role": "expert",
                    "profession": expert.get("profession", ""),
                    "title": expert.get("title", ""),
                    "stance": expert.get("stance", ""),
                    "color": expert.get("color", "#3B82F6"),
                    "discussion_id": discussion_id,
                }
            )

        # 4. Transition to PENDING_CONFIRM.
        _disc_repo.update_status(discussion_id, "PENDING_CONFIRM")

    except HTTPException:
        raise  # re-raise FastAPI errors unchanged
    except Exception as exc:
        logger.exception(
            "Failed to persist experts / update status for discussion %s",
            discussion_id,
        )
        # Rollback: remove any partially created data.
        _expert_repo.delete_by_discussion(discussion_id)
        _disc_repo.delete(discussion_id, "discussion")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create discussion: {exc}",
        )

    # 5. Build roster (moderator first).
    roster = [moderator] + experts

    logger.info("Discussion %s created with %d experts", discussion_id, len(experts))
    return {
        "discussion_id": discussion_id,
        "topic": topic,
        "expert_count": expert_count,
        "status": "PENDING_CONFIRM",
        "roster": roster,
    }


# ═══════════════════════════════════════════════════════════════════
# GET /discussions — list discussions
# ═══════════════════════════════════════════════════════════════════


@discussion_router.get("")
async def list_discussions(
    status: Optional[str] = Query(default=None),
    user_id: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """Return a paginated list of discussions.

    Optionally filter by *status* and/or *user_id*.
    """
    if status:
        items = _disc_repo.list_by_status(status, limit=limit, offset=offset)
    else:
        items = _disc_repo.list_all("discussion", limit=limit, offset=offset)

    # Filter by user_id in Python (repository doesn't support this filter yet).
    if user_id:
        items = [d for d in items if d.get("created_by") == user_id]

    return {"items": items, "total": len(items)}


# ═══════════════════════════════════════════════════════════════════
# GET /discussions/{discussion_id} — discussion detail
# ═══════════════════════════════════════════════════════════════════


@discussion_router.get("/{discussion_id}")
async def get_discussion(discussion_id: str) -> dict[str, Any]:
    """Return the full discussion detail with all related data."""
    detail = _disc_repo.get_detail(discussion_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Discussion not found")
    return detail


# ═══════════════════════════════════════════════════════════════════
# POST /discussions/{discussion_id}/start — start discussion
# ═══════════════════════════════════════════════════════════════════


@discussion_router.post("/{discussion_id}/start")
async def start_discussion(
    discussion_id: str, payload: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    """Confirm the roster (optional micro-adjustment) and start the discussion.

    1. Validate status is PENDING_CONFIRM.
    2. Optionally replace roster if *confirmed_roster* is provided.
    3. Transition to IN_PROGRESS, set started_at.
    4. Initialize the SSE session and launch the speaker loop.
    """
    disc = _disc_repo.get_by_id(discussion_id, "discussion")
    if disc is None:
        raise HTTPException(status_code=404, detail="Discussion not found")
    if disc["status"] != "PENDING_CONFIRM":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot start discussion in status {disc['status']}",
        )

    # Handle optional roster replacement.
    confirmed_roster = (payload or {}).get("confirmed_roster")
    if confirmed_roster:
        _expert_repo.delete_by_discussion(discussion_id)
        for expert in confirmed_roster:
            _expert_repo.create(
                {
                    "id": expert.get("id", str(uuid.uuid4())),
                    "name": expert["name"],
                    "role": expert.get("role", "expert"),
                    "profession": expert.get("profession", ""),
                    "title": expert.get("title", ""),
                    "stance": expert.get("stance", ""),
                    "color": expert.get("color", "#3B82F6"),
                    "discussion_id": discussion_id,
                }
            )

    # Build expert list from DB for session initialization.
    experts_raw = _disc_repo.get_detail(discussion_id)
    experts = experts_raw.get("experts", []) if experts_raw else []

    started_at = datetime.now(timezone.utc).isoformat()
    _disc_repo.update_status(discussion_id, "IN_PROGRESS")

    # Initialize session and start speaker loop.
    session_manager.create_session(discussion_id, experts)
    await session_manager.enqueue_event(
        discussion_id,
        "status_update",
        {
            "discussion_id": discussion_id,
            "previous_status": "PENDING_CONFIRM",
            "status": "IN_PROGRESS",
        },
    )
    asyncio.create_task(_speaker_engine.start_discussion(discussion_id))

    logger.info("Discussion %s started", discussion_id)
    return {
        "discussion_id": discussion_id,
        "status": "IN_PROGRESS",
        "started_at": started_at,
    }


# ═══════════════════════════════════════════════════════════════════
# POST /discussions/{discussion_id}/end — end discussion
# ═══════════════════════════════════════════════════════════════════


@discussion_router.post("/{discussion_id}/end")
async def end_discussion(discussion_id: str) -> dict[str, Any]:
    """End an in-progress discussion.

    1. Validate status is IN_PROGRESS.
    2. Signal the speaker loop to stop.
    3. Generate a moderator summary via LLM.
    4. Persist summary + transition to COMPLETED.
    5. Broadcast summary SSE event and close the stream.
    """
    disc = _disc_repo.get_by_id(discussion_id, "discussion")
    if disc is None:
        raise HTTPException(status_code=404, detail="Discussion not found")
    if disc["status"] != "IN_PROGRESS":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot end discussion in status {disc['status']}",
        )

    # Stop the speaker loop and get summary.
    result = await _speaker_engine.end_discussion(discussion_id)
    summary_text = result.get("summary", "") if result else ""

    ended_at = datetime.now(timezone.utc).isoformat()

    # Persist summary and status.
    # We use raw connection for the update since DiscussionRepository
    # doesn't have a direct method for this combo.
    from app.database import get_db_connection

    with get_db_connection() as conn:
        conn.execute(
            "UPDATE discussion SET status = ?, summary = ?, ended_at = ? WHERE id = ?",
            ("COMPLETED", summary_text, ended_at, discussion_id),
        )

    # Clean up session.
    session_manager.remove_session(discussion_id)

    logger.info("Discussion %s ended", discussion_id)
    return {
        "discussion_id": discussion_id,
        "status": "COMPLETED",
        "summary": summary_text,
        "ended_at": ended_at,
    }


# ═══════════════════════════════════════════════════════════════════
# POST /discussions/{discussion_id}/ask — user asks an expert
# ═══════════════════════════════════════════════════════════════════


@discussion_router.post("/{discussion_id}/ask")
async def ask_expert(
    discussion_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Let a user ask a question to a random (or specified) expert.

    **Flow**
    1. Validate the discussion exists and is IN_PROGRESS.
    2. Verify the SSE session is alive.
    3. Extract *question* from the payload (required).
    4. Pick a non-moderator expert (use *expert_id* if provided).
    5. Call LLM to generate an answer.
    6. Persist the answer as a transcript and broadcast via SSE.
    7. Return the answer speech.
    """
    disc = _disc_repo.get_by_id(discussion_id, "discussion")
    if disc is None:
        raise HTTPException(status_code=404, detail="Discussion not found")
    if disc["status"] != "IN_PROGRESS":
        raise HTTPException(
            status_code=400,
            detail=f"Discussion is not in progress (status={disc['status']})",
        )

    sess = session_manager.get_session(discussion_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="Session not found")

    question: str = (payload.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    # Pick the answering expert.
    requested_expert_id = payload.get("expert_id")
    candidates = [
        e for e in sess.experts if e.get("role") != "moderator"
    ]
    if not candidates:
        raise HTTPException(
            status_code=400, detail="No experts available to answer"
        )

    if requested_expert_id:
        expert = next(
            (e for e in candidates if e["id"] == requested_expert_id), None
        )
        if expert is None:
            raise HTTPException(
                status_code=400,
                detail=f"Expert {requested_expert_id} not found",
            )
    else:
        expert = random.choice(candidates)

    # Generate the expert's answer.
    # Intentionally omit discussion topic and history — the expert
    # should answer the user's question directly.
    try:
        answer_text = await _llm_client.generate_answer(
            question=question,
            expert=expert,
        )
    except Exception as exc:
        logger.exception("LLM answer generation failed for discussion %s", discussion_id)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate expert answer: {exc}",
        )

    # Persist as a transcript.
    speech_data: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "content": answer_text,
        "speaker_id": expert["id"],
        "discussion_id": discussion_id,
        "speech_type": "main",
        "is_user_question": True,
    }
    transcript = _transcript_repo.create(speech_data)

    # Enrich with speaker metadata for the SSE event.
    transcript["speaker_name"] = expert.get("name")
    transcript["speaker_color"] = expert.get("color")
    transcript["is_user_question"] = True

    # Broadcast via SSE so all viewers see the answer.
    await session_manager.enqueue_event(discussion_id, "speech", transcript)

    logger.info(
        "Expert %s answered user question in discussion %s",
        expert.get("name"),
        discussion_id,
    )
    return {"status": "answered", "speech": transcript}


# ═══════════════════════════════════════════════════════════════════
# POST /discussions/{discussion_id}/regenerate-roster
# ═══════════════════════════════════════════════════════════════════


@discussion_router.post("/{discussion_id}/regenerate-roster")
async def regenerate_roster(discussion_id: str) -> dict[str, Any]:
    """Re-generate the expert roster for a PENDING_CONFIRM discussion.

    1. Validate status is PENDING_CONFIRM.
    2. Delete existing experts.
    3. Call LLM to generate a new roster.
    4. Persist new experts.
    5. Return the new roster.
    """
    disc = _disc_repo.get_by_id(discussion_id, "discussion")
    if disc is None:
        raise HTTPException(status_code=404, detail="Discussion not found")
    if disc["status"] != "PENDING_CONFIRM":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot regenerate roster in status {disc['status']}. "
                f"Must be PENDING_CONFIRM."
            ),
        )

    # Delete old experts.
    _expert_repo.delete_by_discussion(discussion_id)

    topic = disc["topic"]
    expert_count = disc["expert_count"]

    # Regenerate.
    try:
        roster_result = await _llm_client.generate_roster(topic, expert_count)
    except Exception as exc:
        logger.exception(
            "Failed to regenerate roster for discussion %s", discussion_id
        )
        raise HTTPException(
            status_code=500,
            detail=f"LLM roster generation failed: {exc}",
        )

    moderator = roster_result["moderator"]
    experts = roster_result.get("experts", [])

    # Persist.
    _expert_repo.create(
        {
            "id": moderator.get("id", str(uuid.uuid4())),
            "name": moderator["name"],
            "role": "moderator",
            "profession": moderator.get("profession", ""),
            "title": moderator.get("title", ""),
            "stance": moderator.get("stance", ""),
            "color": moderator.get("color", "#6B7280"),
            "discussion_id": discussion_id,
        }
    )
    for expert in experts:
        _expert_repo.create(
            {
                "id": expert.get("id", str(uuid.uuid4())),
                "name": expert["name"],
                "role": "expert",
                "profession": expert.get("profession", ""),
                "title": expert.get("title", ""),
                "stance": expert.get("stance", ""),
                "color": expert.get("color", "#3B82F6"),
                "discussion_id": discussion_id,
            }
        )

    roster = [moderator] + experts
    logger.info("Roster regenerated for discussion %s", discussion_id)
    return {
        "discussion_id": discussion_id,
        "topic": topic,
        "expert_count": expert_count,
        "status": "PENDING_CONFIRM",
        "roster": roster,
    }


# ═══════════════════════════════════════════════════════════════════
# GET /discussions/{discussion_id}/stream — SSE
# ═══════════════════════════════════════════════════════════════════


@discussion_router.get("/{discussion_id}/stream")
async def stream_discussion(
    discussion_id: str, request: Request
) -> StreamingResponse:
    """Subscribe to real-time discussion events via Server-Sent Events.

    Event types: ``speech``, ``status_update``, ``consensus_update``,
    ``divergence_update``, ``summary`` (final event — stream closes after).
    """

    async def event_generator():
        sess = session_manager.get_session(discussion_id)
        if sess is None:
            # Session not yet initialised; yield an error and exit.
            error_envelope = {
                "event": "error",
                "discussion_id": discussion_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {"message": "Session not found"},
            }
            yield f"data: {json.dumps(error_envelope, ensure_ascii=False)}\n\n"
            return

        queue = sess.transcript_queue

        try:
            while True:
                # Check client disconnect.
                if await request.is_disconnected():
                    break

                try:
                    envelope = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    # Send keep-alive comment.
                    yield ": keepalive\n\n"
                    continue

                event_type = envelope["event"]
                payload = json.dumps(envelope, ensure_ascii=False)
                yield f"event: {event_type}\ndata: {payload}\n\n"

                # After summary, close the stream.
                if event_type == "summary":
                    break

        except asyncio.CancelledError:
            logger.debug("SSE stream cancelled for discussion %s", discussion_id)
        finally:
            logger.debug("SSE stream closed for discussion %s", discussion_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
