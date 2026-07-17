"""Transcript Pydantic 模型 — 对齐 api-spec.yaml components/schemas/Transcript。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .common import SpeechType


class TranscriptBase(BaseModel):
    """发言基础字段（写入时使用）。"""

    content: str = Field(..., min_length=1, description="发言原文")
    speaker_id: str = Field(..., description="发言人 ID → expert.id")
    discussion_id: str = Field(..., description="所属讨论 ID")
    speech_type: SpeechType = Field(default=SpeechType.MAIN, description="发言类型")
    reply_to_id: Optional[str] = Field(
        default=None,
        description="反驳/补充时必填，指向被回复的发言 ID",
    )
    sequence: int = Field(
        ...,
        ge=0,
        description="讨论内递增序号，由 Repository 层按 discussion_id 分组生成，不可依赖时间戳排序",
    )


class Transcript(TranscriptBase):
    """完整发言模型（含冗余展示字段）。"""

    id: str = Field(..., description="UUID v4 唯一标识")
    speaker_name: Optional[str] = Field(
        default=None, description="发言人姓名（冗余，减少前端 JOIN）"
    )
    speaker_color: Optional[str] = Field(
        default=None, description="发言人颜色（冗余）"
    )
    created_at: datetime = Field(..., description="发言时间戳（ISO 8601）")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")
