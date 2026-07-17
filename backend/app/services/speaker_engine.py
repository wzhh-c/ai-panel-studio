# -*- coding: utf-8 -*-
"""Async speaker engine — drives the expert speech loop for each discussion.

A background ``asyncio.Task`` is spawned per discussion.  It manages the
full lifecycle: moderator opening → round-robin expert speeches →
consensus/divergence detection → moderator closing (on stop signal).
"""

import asyncio
import json
import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.llm.client import DeepSeekClient
from app.repositories.consensus_repository import ConsensusRepository
from app.repositories.divergence_repository import DivergenceRepository
from app.repositories.transcript_repository import TranscriptRepository
from app.services.session_manager import SessionManager, session_manager

logger = logging.getLogger(__name__)

# How many speeches between consensus/divergence analysis rounds.
ANALYSIS_INTERVAL = 3

# How many expert speeches between moderator interventions.
MODERATOR_INTERVAL = 3

# Speech interval range (seconds).
SPEECH_MIN_DELAY = 2.0
SPEECH_MAX_DELAY = 5.0


class SpeakerEngine:
    """Coordinates the async speech loop for a single discussion.

    Args:
        llm_client: DeepSeek client (mock or real).
        transcript_repo: TranscriptRepository instance.
        consensus_repo: ConsensusRepository instance.
        divergence_repo: DivergenceRepository instance.
        sm: SessionManager singleton.
    """

    def __init__(
        self,
        llm_client: Optional[DeepSeekClient] = None,
        transcript_repo: Optional[TranscriptRepository] = None,
        consensus_repo: Optional[ConsensusRepository] = None,
        divergence_repo: Optional[DivergenceRepository] = None,
        sm: Optional[SessionManager] = None,
    ) -> None:
        self._llm = llm_client or DeepSeekClient()
        self._transcript_repo = transcript_repo or TranscriptRepository()
        self._consensus_repo = consensus_repo or ConsensusRepository()
        self._divergence_repo = divergence_repo or DivergenceRepository()
        self._sm: SessionManager = sm or session_manager

    # ── public API ──────────────────────────────────────────────

    async def start_discussion(self, discussion_id: str) -> None:
        """Launch the background speech loop for a discussion.

        Safe to call multiple times — subsequent calls are no-ops if the
        session is already running.
        """
        sess = self._sm.get_session(discussion_id)
        if sess is None:
            logger.error("No session found for discussion %s", discussion_id)
            return
        if sess.running:
            logger.warning("Discussion %s is already running", discussion_id)
            return

        sess.running = True
        sess.stop_event.clear()
        asyncio.create_task(self._speech_loop(discussion_id))
        logger.info("Speaker loop started for discussion %s", discussion_id)

    async def end_discussion(self, discussion_id: str) -> Optional[dict[str, Any]]:
        """Stop the speech loop and generate the moderator's closing summary.

        Returns:
            Summary dict ``{"summary": "..."}`` or ``None`` if the
            session does not exist.
        """
        sess = self._sm.get_session(discussion_id)
        if sess is None:
            logger.error("No session found for discussion %s", discussion_id)
            return None

        # Signal the loop to stop.
        await self._sm.stop_session(discussion_id)

        # Wait briefly for the loop to finish.
        await asyncio.sleep(1.0)
        sess.running = False

        return await self._generate_closing_summary(discussion_id)

    # ── speech loop ─────────────────────────────────────────────

    async def _speech_loop(self, discussion_id: str) -> None:
        """Main loop: opening → expert rounds (with analysis) → graceful exit."""
        sess = self._sm.get_session(discussion_id)
        if sess is None:
            logger.error(f"Session not found for discussion {discussion_id}")
            return

        logger.info(f"Starting speech loop for discussion {discussion_id}")
        logger.info(f"Experts in session: {len(sess.experts)}")
        logger.info(f"Expert names: {[e.get('name') for e in sess.experts]}")

        if not sess.experts:
            logger.warning("No experts in session, attempting to reload from DB")
            from app.repositories.discussion_repository import DiscussionRepository
            detail = DiscussionRepository().get_detail(discussion_id)
            if detail:
                sess.experts = detail.get("experts", [])
                logger.info(f"Reloaded {len(sess.experts)} experts from DB")
            else:
                logger.error("Failed to reload experts from DB")
                return

        try:
            # ── moderator opening ───────────────────────────────
            moderator = self._find_moderator(sess.experts)
            if moderator:
                await self._speak(
                    discussion_id, moderator, speech_type="main", is_opening=True
                )

            speech_count = 0
            expert_count = 0  # track expert-only speeches for moderator pacing

            while not sess.stop_event.is_set():
                # Pick a random expert (non-moderator).
                expert = self._pick_random_expert(sess.experts)
                if expert is None:
                    await asyncio.sleep(1)
                    continue

                await self._speak(discussion_id, expert)
                speech_count += 1
                expert_count += 1

                # Periodic consensus/divergence analysis.
                if speech_count % ANALYSIS_INTERVAL == 0:
                    await self._analyse_discussion(discussion_id)

                # Moderator intervention every N *expert* speeches.
                if expert_count % MODERATOR_INTERVAL == 0:
                    moderator = self._find_moderator(sess.experts)
                    if moderator:
                        await self._moderator_intervene(discussion_id, moderator)
                        speech_count += 1

                # Random delay between speeches.
                delay = random.uniform(SPEECH_MIN_DELAY, SPEECH_MAX_DELAY)
                # Check stop_event with timeout.
                try:
                    await asyncio.wait_for(
                        sess.stop_event.wait(), timeout=delay
                    )
                    # If we get here, stop_event was set during the wait.
                    break
                except asyncio.TimeoutError:
                    # Normal — delay elapsed, continue looping.
                    pass

        except Exception:
            logger.exception(
                "Speaker loop crashed for discussion %s", discussion_id
            )
        finally:
            logger.info("Speaker loop exited for discussion %s", discussion_id)

    # ── speech generation ───────────────────────────────────────

    async def _speak(
        self,
        discussion_id: str,
        speaker: dict[str, Any],
        speech_type: str = "main",
        is_opening: bool = False,
    ) -> Optional[dict[str, Any]]:
        """Generate, persist, and broadcast a single speech."""
        sess = self._sm.get_session(discussion_id)
        if sess is None:
            return None

        # Build transcript history.
        history = self._transcript_repo.list_by_discussion(discussion_id)

        # Generate speech content.
        if is_opening:
            content = (
                f"各位专家，欢迎来到今天的圆桌讨论。"
                f"我是主持人{speaker.get('name', '')}。"
                f"今天我们讨论的话题既重要又复杂，"
                f"期待听到各位多元的观点和见解。"
                f"让我们开始吧。"
            )
            speech_result = {"content": content, "speech_type": "main"}
        else:
            speech_result = await self._llm.generate_speech(
                history, speaker, ""
            )

        # 处理 speech_type 和 reply_to_id
        speech_type_val = speech_result.get("speech_type", "main")
        reply_to_id = None

        # 如果类型是 supplement 或 rebuttal，必须指定 reply_to_id
        if speech_type_val in ("supplement", "rebuttal"):
            # 从历史中随机选一条发言作为回复目标
            if history:
                # 从最近的 5 条中随机选（如果总数少于5则从全部中选）
                recent = history[-5:] if len(history) >= 5 else history
                target = random.choice(recent)
                reply_to_id = target["id"]
            else:
                # 没有历史，强制改为 main
                speech_type_val = "main"

        # Persist.
        data = {
            "id": str(uuid.uuid4()),
            "content": speech_result["content"],
            "speaker_id": speaker["id"],
            "discussion_id": discussion_id,
            "speech_type": speech_type_val,
        }
        if reply_to_id:
            data["reply_to_id"] = reply_to_id

        transcript = self._transcript_repo.create(data)

        # Enrich with speaker metadata for SSE.
        transcript["speaker_name"] = speaker.get("name")
        transcript["speaker_color"] = speaker.get("color")

        # Broadcast via SSE.
        await self._sm.enqueue_event(discussion_id, "speech", transcript)

        logger.debug(
            "Speech [seq=%s] by %s in discussion %s",
            transcript.get("sequence"),
            speaker.get("name"),
            discussion_id,
        )
        return transcript

    # ── moderator intervention ───────────────────────────────────

    async def _moderator_intervene(
        self,
        discussion_id: str,
        moderator: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        """Let the moderator ask a follow-up question or connect viewpoints.

        Picks a random expert to address, generates a short intervention,
        persists and broadcasts it via SSE.
        """
        sess = self._sm.get_session(discussion_id)
        if sess is None:
            return None

        history = self._transcript_repo.list_by_discussion(discussion_id)

        # Pick a non-moderator expert to address.
        candidates = [
            e for e in sess.experts if e.get("role") != "moderator"
        ]
        target = random.choice(candidates) if candidates else None

        # Build an intervention instruction (passed as the "topic" to the LLM).
        if target:
            prompt = (
                f"（作为主持人进行讨论串联）请根据刚才的发言内容，"
                f"向{target['name']}专家提出一个简短的追问或邀请其回应，"
                f"控制在1-2句话内。语气自然、有温度，像真实圆桌讨论中的主持人。"
            )
        else:
            prompt = (
                f"（作为主持人进行讨论串联）请根据刚才的发言内容，"
                f"对不同专家的观点做简短串联总结，"
                f"控制在1-2句话内。语气自然、有温度。"
            )

        speech_result = await self._llm.generate_speech(
            history, moderator, prompt
        )

        # Persist.
        data = {
            "id": str(uuid.uuid4()),
            "content": speech_result["content"],
            "speaker_id": moderator["id"],
            "discussion_id": discussion_id,
            "speech_type": "main",
        }

        transcript = self._transcript_repo.create(data)

        # Enrich with speaker metadata for SSE.
        transcript["speaker_name"] = moderator.get("name")
        transcript["speaker_color"] = moderator.get("color")

        # Broadcast via SSE.
        await self._sm.enqueue_event(discussion_id, "speech", transcript)

        logger.debug(
            "Moderator intervened [seq=%s] in discussion %s",
            transcript.get("sequence"),
            discussion_id,
        )
        return transcript

    # ── analysis ────────────────────────────────────────────────

    async def _analyse_discussion(self, discussion_id: str) -> None:
        """Analyze recent transcripts for consensus/divergence.

        In production this would call the LLM.  The mock implementation
        generates simple synthetic consensus/divergence records.
        """
        transcripts = self._transcript_repo.list_by_discussion(discussion_id)
        if len(transcripts) < 2:
            return

        existing_consensus = self._consensus_repo.get_by_discussion(discussion_id)
        existing_divergence = self._divergence_repo.get_by_discussion(discussion_id)

        # Create a new consensus every analysis round (simplified).
        cid = str(uuid.uuid4())
        c_ids = json.dumps([t["id"] for t in transcripts[-2:]])
        consensus_data = {
            "id": cid,
            "content": (
                f"专家们一致认为需要对现有框架进行进一步的审视和讨论，"
                f"在核心议题上达成了初步共识。"
            ),
            "discussion_id": discussion_id,
            "source_transcript_ids": c_ids,
        }
        consensus = self._consensus_repo.create(consensus_data)
        await self._sm.enqueue_event(
            discussion_id, "consensus_update",
            {**consensus, "action": "created"},
        )

        # Create a divergence if none exists yet.
        if len(existing_divergence) == 0:
            did = str(uuid.uuid4())
            d_ids = json.dumps([t["id"] for t in transcripts[-2:]])
            divergence_data = {
                "id": did,
                "content": (
                    "核心分歧：关于未来发展路径的选择——"
                    "是优先完善制度框架，还是优先推动技术创新。"
                ),
                "discussion_id": discussion_id,
                "sides": json.dumps(
                    [
                        {
                            "expert_id": transcripts[-1].get("speaker_id", ""),
                            "stance_label": "制度优先",
                            "summary": "主张先建立清晰的制度框架，确保发展有序。",
                        },
                        {
                            "expert_id": transcripts[-2].get("speaker_id", ""),
                            "stance_label": "创新优先",
                            "summary": "认为应优先推动技术进步，在实践中逐步完善制度。",
                        },
                    ]
                ),
                "source_transcript_ids": d_ids,
            }
            divergence = self._divergence_repo.create(divergence_data)
            await self._sm.enqueue_event(
                discussion_id, "divergence_update",
                {**divergence, "action": "created"},
            )

        logger.debug(
            "Analysis complete for discussion %s (%d transcripts)",
            discussion_id,
            len(transcripts),
        )

    # ── closing ─────────────────────────────────────────────────

    async def _generate_closing_summary(
        self, discussion_id: str
    ) -> Optional[dict[str, Any]]:
        """Generate and broadcast the moderator's closing summary."""
        sess = self._sm.get_session(discussion_id)
        if sess is None:
            return None

        moderator = self._find_moderator(sess.experts)
        moderator_name = moderator.get("name", "Moderator") if moderator else "Moderator"

        transcripts = self._transcript_repo.list_by_discussion(discussion_id)
        consensus_list = self._consensus_repo.get_by_discussion(discussion_id)
        divergence_list = self._divergence_repo.get_by_discussion(discussion_id)

        result = await self._llm.generate_summary(
            moderator_name, transcripts, consensus_list, divergence_list
        )

        # Broadcast summary event.
        summary_data = {
            "discussion_id": discussion_id,
            "summary": result["summary"],
            "ended_at": datetime.now(timezone.utc).isoformat(),
        }
        await self._sm.enqueue_event(discussion_id, "summary", summary_data)

        logger.info("Closing summary generated for discussion %s", discussion_id)
        return result

    # ── helpers ─────────────────────────────────────────────────

    @staticmethod
    def _find_moderator(
        experts: list[dict[str, Any]],
    ) -> Optional[dict[str, Any]]:
        """Return the moderator from the expert list, or ``None``."""
        for e in experts:
            if e.get("role") == "moderator":
                return e
        return None

    @staticmethod
    def _pick_random_expert(
        experts: list[dict[str, Any]],
    ) -> Optional[dict[str, Any]]:
        """Pick a random non-moderator expert."""
        candidates = [e for e in experts if e.get("role") != "moderator"]
        logger.debug(f"Expert candidates: {len(candidates)} out of {len(experts)}")
        if not candidates:
            logger.warning("No non-moderator experts available for speech")
            return None
        return random.choice(candidates)