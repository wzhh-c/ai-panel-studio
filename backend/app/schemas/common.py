"""通用枚举与响应模型 — 对齐 api-spec.yaml components/schemas。"""

from enum import StrEnum
from typing import Any, Optional

from pydantic import BaseModel


# ── 枚举 ──────────────────────────────────────────────────


class DiscussionStatus(StrEnum):
    """讨论生命周期状态。"""

    GENERATING = "GENERATING"
    PENDING_CONFIRM = "PENDING_CONFIRM"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class ExpertRole(StrEnum):
    """专家角色。"""

    MODERATOR = "moderator"
    EXPERT = "expert"


class SpeechType(StrEnum):
    """发言类型。"""

    MAIN = "main"
    SUPPLEMENT = "supplement"
    REBUTTAL = "rebuttal"
    QUESTION = "question"


class ExpertStatus(StrEnum):
    """专家实时状态（SSE 推送）。"""

    TYPING = "typing"
    IDLE = "idle"
    SPEAKING = "speaking"


class ConsensusAction(StrEnum):
    """共识事件操作类型。"""

    CREATED = "created"
    UPDATED = "updated"


class DivergenceAction(StrEnum):
    """分歧事件操作类型。"""

    CREATED = "created"
    UPDATED = "updated"


# ── 通用响应 ──────────────────────────────────────────────


class ErrorResponse(BaseModel):
    """标准错误响应。"""

    error: str
    message: str
    details: Optional[dict[str, Any]] = None
