# -*- coding: utf-8 -*-
"""DeepSeek API client with Mock fallback for testing.

Set ``USE_MOCK_LLM=true`` to bypass real API calls.
"""

import json
import logging
import os
import random
import uuid
from typing import Any, Optional

import httpx

from app.config import settings
from app.exceptions import RepositoryError

logger = logging.getLogger(__name__)

# ── preset colour palette (avoid duplicates) ──────────────────
COLOUR_PALETTE = [
    "#3B82F6",  # blue
    "#EF4444",  # red
    "#10B981",  # green
    "#F59E0B",  # amber
    "#8B5CF6",  # violet
    "#EC4899",  # pink
    "#06B6D4",  # cyan
    "#F97316",  # orange
    "#84CC16",  # lime
    "#6366F1",  # indigo
]


class LLMTimeoutError(RepositoryError):
    """Raised when an LLM API call exceeds the configured timeout."""


class LLMError(RepositoryError):
    """Raised for general LLM API failures."""


class DeepSeekClient:
    """Async client for the DeepSeek chat-completion API.

    Supports two modes, controlled by the ``USE_MOCK_LLM`` env var:

    * **mock** — returns canned, deterministic responses (useful for tests).
    * **real** — calls the live DeepSeek API via ``httpx.AsyncClient``.
    """

    def __init__(self) -> None:
        self._mock = os.getenv("USE_MOCK_LLM", "false").lower() == "true"
        self._api_key: str = settings.DEEPSEEK_API_KEY
        self._base_url: str = settings.DEEPSEEK_BASE_URL.rstrip("/")
        self._model: str = settings.LLM_MODEL
        self._timeout: float = 60.0
        self._colour_index: int = 0
        logger.info(
            "DeepSeekClient initialized (mock=%s, model=%s)", self._mock, self._model
        )

    # ── public API ──────────────────────────────────────────────

    async def generate_roster(
        self, topic: str, expert_count: int
    ) -> dict[str, Any]:
        """Generate 1 moderator + *expert_count* experts for a topic.

        Returns:
            ``{"moderator": {...}, "experts": [...]}``
        """
        if self._mock:
            return self._mock_roster(topic, expert_count)
        return await self._real_roster(topic, expert_count)

    async def generate_speech(
        self,
        transcript_history: list[dict[str, Any]],
        speaker: dict[str, Any],
        discussion_topic: str,
    ) -> dict[str, Any]:
        """Generate the next speech for an expert.

        Returns:
            ``{"content": "...", "speech_type": "main|supplement|rebuttal"}``
        """
        if self._mock:
            return self._mock_speech(speaker, discussion_topic)
        return await self._real_speech(transcript_history, speaker, discussion_topic)

    async def generate_summary(
        self,
        moderator_name: str,
        transcripts: list[dict[str, Any]],
        consensus_list: list[dict[str, Any]],
        divergence_list: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Generate a natural-language moderator summary (no JSON)."""
        if self._mock:
            return self._mock_summary(moderator_name)
        return await self._real_summary(
            moderator_name, transcripts, consensus_list, divergence_list
        )

    async def generate_answer(
        self,
        question: str,
        expert: dict[str, Any],
    ) -> str:
        """Generate an expert's answer to a user question.

        Intentionally ignores discussion topic and transcript history —
        the expert answers the question directly, without drifting back
        to the ongoing discussion.

        Args:
            question: The user's question.
            expert: The expert answering (name, profession, stance, color, …).

        Returns:
            A natural Chinese answer string (1–3 sentences).
        """
        if self._mock:
            return self._mock_answer(question, expert)
        return await self._real_answer(question, expert)

    # ── mock implementations ────────────────────────────────────

    def _mock_roster(self, topic: str, expert_count: int) -> dict[str, Any]:
        """Return a canned roster with diverse stances."""
        stances_pool = [
            ("支持者", "坚定支持，认为机遇远大于风险"),
            ("谨慎乐观", "总体看好但认为需要审慎推进"),
            ("怀疑者", "持怀疑态度，强调潜在风险"),
            ("中立者", "保持中立，倡导平衡发展"),
            ("务实派", "务实派——聚焦落地可行性与执行细节"),
            ("反对者", "基于伦理考量坚决反对"),
            ("改革派", "支持改革但反对激进变革"),
            ("未来派", "对长期潜力持乐观态度"),
        ]
        professions = [
            ("法学教授", "Professor of Law"),
            ("技术伦理学家", "Technology Ethicist"),
            ("AI企业家", "AI Entrepreneur"),
            ("社会学家", "Sociologist"),
            ("经济学家", "Economist"),
            ("计算机科学家", "Computer Scientist"),
            ("哲学家", "Philosopher"),
            ("政策顾问", "Policy Advisor"),
            ("心理学家", "Psychologist"),
        ]
        names = [
            ("林浩然", "Lin Haoran"),
            ("苏婉清", "Su Wanqing"),
            ("赵承宇", "Zhao Chengyu"),
            ("周明远", "Zhou Mingyuan"),
            ("陈思齐", "Chen Siqi"),
            ("王若溪", "Wang Ruoxi"),
            ("张启航", "Zhang Qihang"),
            ("李雪凝", "Li Xuening"),
            ("刘知行", "Liu Zhixing"),
        ]

        self._colour_index = 0

        moderator = {
            "id": str(uuid.uuid4()),
            "name": names[0][0],
            "role": "moderator",
            "profession": "科技媒体主编",
            "title": "《前沿对话》栏目首席主持人",
            "stance": "中立引导者——促进各方平衡讨论",
            "color": self._next_colour(),
        }

        experts: list[dict[str, Any]] = []
        used_stances: list[int] = []
        for i in range(min(expert_count, len(names) - 1)):
            si = i % len(stances_pool)
            used_stances.append(si)
            pi = (i + 1) % len(professions)
            experts.append(
                {
                    "id": str(uuid.uuid4()),
                    "name": names[i + 1][0],
                    "role": "expert",
                    "profession": professions[pi][0],
                    "title": f"{professions[pi][1]} — {professions[pi][0]}",
                    "stance": stances_pool[si][1],
                    "color": self._next_colour(),
                }
            )

        logger.debug("Mock roster generated: 1 moderator + %d experts", len(experts))
        return {"moderator": moderator, "experts": experts}

    def _mock_speech(
        self, speaker: dict[str, Any], topic: str
    ) -> dict[str, Any]:
        """Return a short canned speech (English for encoding safety)."""
        name = speaker.get("name", "Expert")
        speeches = [
            f'关于“{topic}”，我认为我们需要多维度分析，'
            f'而不是简单的二元判断。',
            f'我部分同意前面的观点，但想补充的是，'
            f'技术可行性与伦理边界必须同步推进。',
            f'恕我不能完全认同。现有框架已经提供了足够的弹性，'
            f'过度监管反而会扼杀创新活力。',
            f'从实践角度来看，{topic}的核心挑战不在于理论层面，'
            f'而在于如何在落地过程中平衡各方利益。',
        ]
        types = ["main", "supplement", "rebuttal", "question"]
        return {
            "content": f"【{name}】：{random.choice(speeches)}",
            "speech_type": random.choice(types),
        }

    def _mock_summary(self, moderator_name: str) -> dict[str, Any]:
        """Return a canned natural-language summary."""
        return {
            "summary": (
                f"感谢各位专家的精彩讨论。经过深入交流，"
                f"我们在几个核心问题上达成了共识："
                f"第一，现有制度框架确实需要进一步完善；"
                f"第二，技术发展的速度远超制度更新的步伐，"
                f"需要建立更敏捷的响应机制。"
                f"同时，我们也看到了明显的分歧——"
                f"尤其是在制度严谨性与创新自由度之间的平衡上。"
                f"正是这种多元视角的碰撞，"
                f"让我们对这个议题有了更全面的认识。"
                f"感谢各位的参与。——{moderator_name}"
            )
        }

    def _mock_answer(
        self, question: str, expert: dict[str, Any]
    ) -> str:
        """Return a canned Chinese answer for the user's question."""
        name = expert.get("name", "Expert")
        profession = expert.get("profession", "学者")
        answers = [
            (
                f'关于"{question}"这个问题，从{profession}的角度来看，'
                f"我认为关键在于平衡多方利益，不能简单地下结论。"
                f"我们需要在实践和理论之间找到一个可持续发展的中间地带。"
            ),
            (
                f"这是个很好的问题。作为{profession}，我倾向于认为"
                f"现有框架虽然不完美，但提供了足够的弹性来应对新挑战。"
                f"关键是执行层面如何落实。"
            ),
            (
                f"感谢提问。我个人的观点是，我们需要更务实地看待这个问题——"
                f"理论上的完美方案在实践中往往难以落地。"
                f"建议从具体案例出发逐步推进。"
            ),
        ]
        return f"[{name}]: {random.choice(answers)}"

    # ── real API calls ──────────────────────────────────────────

    async def _real_roster(self, topic: str, expert_count: int) -> dict[str, Any]:
        """Call DeepSeek to generate a roster."""
        prompt = self._build_roster_prompt(topic, expert_count)
        raw = await self._call_api(prompt)
        return self._parse_json_response(raw, "roster")

    async def _real_speech(
        self,
        transcript_history: list[dict[str, Any]],
        speaker: dict[str, Any],
        discussion_topic: str,
    ) -> dict[str, Any]:
        """Call DeepSeek to generate a speech."""
        prompt = self._build_speech_prompt(
            transcript_history, speaker, discussion_topic
        )
        raw = await self._call_api(prompt)
        return self._parse_json_response(raw, "speech")

    async def _real_summary(
        self,
        moderator_name: str,
        transcripts: list[dict[str, Any]],
        consensus_list: list[dict[str, Any]],
        divergence_list: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Call DeepSeek to generate a plain-text summary."""
        prompt = self._build_summary_prompt(
            moderator_name, transcripts, consensus_list, divergence_list
        )
        raw = await self._call_api(prompt, expect_json=False)
        return {"summary": raw.strip()}

    async def _real_answer(
        self,
        question: str,
        expert: dict[str, Any],
    ) -> str:
        """Call DeepSeek to generate an expert answer (plain text)."""
        prompt = self._build_answer_prompt(question, expert)
        raw = await self._call_api(prompt, expect_json=False)
        return raw.strip()

    # ── prompt builders ─────────────────────────────────────────

    @staticmethod
    def _build_roster_prompt(topic: str, expert_count: int) -> str:
        return (
            f"You are a discussion organiser. Generate a roster of 1 moderator "
            f"and {expert_count} experts for a roundtable on: {topic}.\n\n"
            "Requirements:\n"
            "- Moderator: neutral facilitator, guides discussion.\n"
            "- Experts: diverse stances (at least support, oppose, and neutral).\n"
            "- Each person must have: name (Chinese), profession, title, stance, color (hex).\n"
            "- Colors: assign from a palette, no duplicates.\n\n"
            "Return ONLY valid JSON (no markdown, no extra text):\n"
            '{"moderator": {"name":..., "profession":..., "title":..., '
            '"stance":..., "color":"#xxx"}, '
            '"experts": [{"name":..., "profession":..., "title":..., '
            '"stance":..., "color":"#xxx"}, ...]}'
        )

    @staticmethod
    def _build_speech_prompt(
        transcript_history: list[dict[str, Any]],
        speaker: dict[str, Any],
        discussion_topic: str,
    ) -> str:
        history_text = "\n".join(
            f"[{t.get('speaker_id','?')}]: {t.get('content','')}"
            for t in transcript_history[-10:]
        ) or "(no prior speeches)"
        return (
            f"You are {speaker.get('name','an expert')}, "
            f"a {speaker.get('profession','thinker')}. "
            f"Your stance: {speaker.get('stance','neutral')}.\n\n"
            f"Discussion topic: {discussion_topic}\n\n"
            f"Recent transcript:\n{history_text}\n\n"
            "Based on the discussion so far, decide whether to:\n"
            "- main: introduce a new point\n"
            "- supplement: build on a prior point\n"
            "- rebuttal: disagree with a prior point\n"
            "- question: pose a question\n\n"
            "Generate a short speech (1-2 sentences, ~30-50 Chinese characters). "
            "Return ONLY valid JSON:\n"
            '{"content": "...", "speech_type": "main|supplement|rebuttal|question"}'
        )

    @staticmethod
    def _build_summary_prompt(
        moderator_name: str,
        transcripts: list[dict[str, Any]],
        consensus_list: list[dict[str, Any]],
        divergence_list: list[dict[str, Any]],
    ) -> str:
        transcript_text = "\n".join(
            f"[{t.get('speaker_id','?')}]: {t.get('content','')}"
            for t in transcripts[-30:]
        )
        consensus_text = "\n".join(
            f"- {c.get('content','')}" for c in consensus_list
        ) or "(none)"
        divergence_text = "\n".join(
            f"- {d.get('content','')}" for d in divergence_list
        ) or "(none)"
        return (
            f"You are {moderator_name}, the moderator of a roundtable discussion.\n\n"
            f"Transcript:\n{transcript_text}\n\n"
            f"Consensus points identified:\n{consensus_text}\n\n"
            f"Divergence points identified:\n{divergence_text}\n\n"
            "Write a natural-language closing summary in the moderator's voice "
            "(Chinese, 150-300 characters). "
            "Cover: key consensus, main divergences, and a gracious closing. "
            "DO NOT output JSON — output plain text only."
        )

    @staticmethod
    def _build_answer_prompt(
        question: str,
        expert: dict[str, Any],
    ) -> str:
        """Build a prompt that asks the expert to answer a user question.

        The prompt intentionally excludes discussion topic and transcript
        history to prevent the model from drifting back to the discussion.
        """
        name = expert.get("name", "an expert")
        profession = expert.get("profession", "thinker")
        stance = expert.get("stance", "neutral")

        return (
            f"你正在参加一场圆桌讨论，但现在有观众向你单独提问。"
            f"请忽略讨论中正在进行的任何话题，"
            f"不要提及任何讨论内容或历史发言，"
            f"只针对观众的问题给出回答。\n\n"
            f"观众问题：{question}\n\n"
            f"你的身份（仅用于回答风格的参考）：\n"
            f"- 姓名：{name}\n"
            f"- 职业：{profession}\n"
            f"- 立场：{stance}\n\n"
            f"回答要求：\n"
            f"- 严格只回答观众问题，不要联系讨论话题\n"
            f"- 如果问题与你的专业领域相关，结合你的立场给出见解\n"
            f"- 如果问题与你的专业完全无关，可以说"
            f"\"我不是这方面的专家，但我认为……\"并给出你的看法\n"
            f"- 回答 1-3 句，约 50-80 字\n"
            f"- 用中文，直接输出纯文本，不要 JSON"
        )

    # ── low-level API call ──────────────────────────────────────

    async def _call_api(
        self, prompt: str, expect_json: bool = True
    ) -> str:
        """Send a chat-completion request and return the message content."""
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if not expect_json:
            payload["temperature"] = 0.7

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                body = resp.json()
                content: str = body["choices"][0]["message"]["content"]
                return content
            except httpx.TimeoutException as exc:
                raise LLMTimeoutError(
                    f"LLM call timed out after {self._timeout}s"
                ) from exc
            except httpx.HTTPStatusError as exc:
                raise LLMError(
                    f"LLM API returned {exc.response.status_code}: "
                    f"{exc.response.text[:200]}"
                ) from exc

    @staticmethod
    def _parse_json_response(raw: str, context: str) -> dict[str, Any]:
        """Extract JSON from an LLM response (may be wrapped in markdown)."""
        text = raw.strip()
        if text.startswith("```"):
            # Strip markdown code fences
            lines = text.split("\n")
            text = "\n".join(
                l for l in lines if not l.startswith("```")
            ).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError(
                f"Failed to parse {context} JSON from LLM response: {exc}"
            ) from exc

    # ── helpers ─────────────────────────────────────────────────

    def _next_colour(self) -> str:
        """Return the next colour from the palette (round-robin)."""
        c = COLOUR_PALETTE[self._colour_index % len(COLOUR_PALETTE)]
        self._colour_index += 1
        return c
