"""Consensus Pydantic 模型 — 对齐 api-spec.yaml components/schemas/Consensus。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Consensus(BaseModel):
    """实时识别的共识点。"""

    id: str = Field(..., description="UUID v4 唯一标识")
    content: str = Field(..., min_length=1, description="共识内容简述")
    discussion_id: str = Field(..., description="所属讨论 ID")
    source_transcript_ids: list[str] = Field(
        ...,
        min_length=2,
        description="关联的发言 ID，至少 2 条",
    )
    created_at: Optional[datetime] = Field(default=None, description="首次识别时间")
    updated_at: datetime = Field(..., description="最后更新时间")


class ConsensusUpdatePayload(Consensus):
    """SSE consensus_update 事件载荷（含 action 标记）。"""

    action: str = Field(..., pattern=r"^(created|updated)$", description="操作类型")
