"""Divergence Pydantic 模型 — 对齐 api-spec.yaml components/schemas/Divergence。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DivergenceSide(BaseModel):
    """分歧中某一方的观点摘要。"""

    expert_id: str = Field(..., description="专家 ID")
    expert_name: Optional[str] = Field(default=None, description="专家姓名")
    expert_color: Optional[str] = Field(default=None, description="专家颜色")
    stance_label: str = Field(..., description="立场标签，如 '支持AI拟制人格'")
    summary: str = Field(..., description="观点摘要")


class Divergence(BaseModel):
    """实时识别的分歧点。"""

    id: str = Field(..., description="UUID v4 唯一标识")
    content: str = Field(..., min_length=1, description="分歧点描述")
    discussion_id: str = Field(..., description="所属讨论 ID")
    sides: list[DivergenceSide] = Field(
        ...,
        min_length=2,
        description="各方观点摘要，至少 2 方",
    )
    source_transcript_ids: list[str] = Field(
        ...,
        min_length=2,
        description="关联的发言 ID，至少 2 条",
    )
    created_at: Optional[datetime] = Field(default=None, description="首次识别时间")
    updated_at: datetime = Field(..., description="最后更新时间")


class DivergenceUpdatePayload(Divergence):
    """SSE divergence_update 事件载荷（含 action 标记）。"""

    action: str = Field(..., pattern=r"^(created|updated)$", description="操作类型")
