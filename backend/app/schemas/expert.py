"""Expert Pydantic 模型 — 对齐 api-spec.yaml components/schemas/Expert。"""

from pydantic import BaseModel, Field

from .common import ExpertRole


class Expert(BaseModel):
    """大模型生成的专家 / 主持人。"""

    id: str = Field(..., description="UUID v4 唯一标识")
    name: str = Field(..., description="专家姓名")
    role: ExpertRole = Field(..., description="角色：moderator 或 expert")
    profession: str = Field(..., description="职业")
    title: str = Field(..., description="头衔 / 称谓")
    stance: str = Field(..., description="立场描述")
    color: str = Field(
        ...,
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="代表色 hex，如 #3B82F6",
    )
