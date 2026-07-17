"""Discussion Pydantic 模型 — 对齐 api-spec.yaml。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .common import DiscussionStatus
from .expert import Expert
from .transcript import Transcript
from .consensus import Consensus
from .divergence import Divergence


# ── 请求体 ────────────────────────────────────────────────


class CreateDiscussionRequest(BaseModel):
    """POST /api/discussions — 创建讨论请求。"""

    topic: str = Field(..., min_length=1, max_length=500, description="讨论话题")
    expert_count: int = Field(
        default=4,
        ge=1,
        le=8,
        description="专家人数 N（不含主持人）",
    )
    user_id: str = Field(..., description="发起人的用户 ID")


class StartDiscussionRequest(BaseModel):
    """POST /api/discussions/{id}/start — 确认阵容（可选微调）。"""

    confirmed_roster: Optional[list[Expert]] = Field(
        default=None,
        description="用户微调后的阵容；不传则直接使用已生成的阵容",
    )


# ── 响应体 ────────────────────────────────────────────────


class CreateDiscussionResponse(BaseModel):
    """POST /api/discussions — 创建成功响应。"""

    discussion_id: str = Field(..., description="讨论 ID")
    topic: str = Field(..., description="讨论话题")
    expert_count: int = Field(..., description="专家人数")
    status: str = Field(default="PENDING_CONFIRM", description="当前状态")
    roster: list[Expert] = Field(
        ..., description="大模型生成的完整阵容（主持人排在首位）"
    )


class StartDiscussionResponse(BaseModel):
    """POST /api/discussions/{id}/start — 开始讨论响应。"""

    discussion_id: str
    status: str = "IN_PROGRESS"
    started_at: datetime


class EndDiscussionResponse(BaseModel):
    """POST /api/discussions/{id}/end — 结束讨论响应。"""

    discussion_id: str
    status: str = "COMPLETED"
    summary: str = Field(..., description="主持人自然语言总结")
    ended_at: datetime


# ── 列表 / 详情 ───────────────────────────────────────────


class DiscussionSummary(BaseModel):
    """讨论列表项（轻量）。"""

    id: str = Field(..., description="讨论 ID")
    topic: str = Field(..., description="讨论话题")
    status: DiscussionStatus = Field(..., description="当前状态")
    expert_count: int = Field(..., description="专家人数")
    summary: Optional[str] = Field(
        default=None, description="主持人总结（仅 COMPLETED 状态有值）"
    )
    created_at: datetime = Field(..., description="创建时间")


class DiscussionListResponse(BaseModel):
    """GET /api/discussions — 讨论列表响应。"""

    items: list[DiscussionSummary]
    total: int


class DiscussionDetail(DiscussionSummary):
    """GET /api/discussions/{id} — 讨论详情（完整）。"""

    created_by: str = Field(..., description="发起用户 ID")
    started_at: Optional[datetime] = Field(default=None, description="开始时间")
    ended_at: Optional[datetime] = Field(default=None, description="结束时间")
    experts: list[Expert] = Field(..., description="参与专家（含主持人）")
    transcripts: list[Transcript] = Field(..., description="全部发言记录")
    consensus_list: list[Consensus] = Field(..., description="当前共识列表")
    divergence_list: list[Divergence] = Field(..., description="当前分歧列表")
