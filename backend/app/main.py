"""FastAPI 应用入口。

挂载健康检查、讨论路由，启动时初始化数据库。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db
from .routers.discussion import discussion_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库。"""
    init_db()
    yield


app = FastAPI(
    title="圆桌讨论系统",
    description="基于大模型生成专家阵容的多方实时讨论平台",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS（开发阶段允许所有来源） ─────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 健康检查 ─────────────────────────────────────────────


@app.get("/health", tags=["System"])
async def health_check():
    """服务健康检查端点。"""
    return {"status": "ok"}


# ── 路由挂载 ─────────────────────────────────────────────

app.include_router(discussion_router, prefix="/api")
