# 圆桌讨论系统 (AI Panel Studio)

基于大语言模型生成专家阵容的多方实时讨论平台。用户输入话题，AI 自动生成持多元立场的专家团队并展开实时辩论，在讨论过程中识别共识与分歧，最后由主持人输出自然语言总结。

---

## 技术选型

| 层级 | 技术 | 版本 |
|------|------|------|
| **后端框架** | FastAPI | ≥0.115.0 |
| **数据库** | SQLite（WAL 模式） | — |
| **LLM** | DeepSeek API（支持 Mock 模式） | — |
| **前端框架** | React + Vite | React 19 / Vite 8 |
| **HTTP 客户端** | Axios | ≥1.18.1 |
| **样式** | Tailwind CSS | ≥4.3.2 |
| **路由** | React Router DOM | ≥7.18.1 |
| **实时通信** | Server-Sent Events (SSE) | — |

---

## 项目结构

```
圆桌讨论/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── config.py            # 环境变量配置
│   │   ├── database.py          # SQLite 连接管理
│   │   ├── exceptions.py        # 自定义异常
│   │   ├── llm/
│   │   │   └── client.py        # DeepSeek API 客户端
│   │   ├── repositories/        # 数据访问层
│   │   ├── routers/
│   │   │   └── discussion.py    # REST API + SSE 端点
│   │   ├── schemas/             # Pydantic 数据模型
│   │   └── services/
│   │       ├── session_manager.py   # 内存会话管理
│   │       └── speaker_engine.py    # 异步发言引擎
│   ├── tests/                   # pytest 测试
│   ├── run.py                   # 启动入口
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/client.js        # Axios 封装 + 拦截器
│   │   ├── hooks/
│   │   │   ├── useDiscussions.js
│   │   │   └── useSSE.js
│   │   ├── pages/
│   │   │   ├── Home.jsx         # 首页（讨论列表）
│   │   │   ├── Discussion.jsx   # 阵容确认页
│   │   │   └── DiscussionRoom.jsx  # 讨论室（三栏布局）
│   │   ├── components/          # 可复用组件
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
├── docs/
│   ├── PRD.md                   # 产品需求文档
│   ├── ER.md                    # ER 图文档
│   ├── API.md                   # API 文档
│   └── ARCHITECTURE.md          # 系统架构文档
├── schema.sql                   # DDL 参考（含触发器和索引）
├── er.mermaid                   # ER 图源文件
├── api-spec.yaml                # OpenAPI 3.0 规范
└── README.md                    # 本文件
```

---

## 环境变量配置

在 `backend/` 目录下创建 `.env` 文件：

```env
# DeepSeek API（必填）
DEEPSEEK_API_KEY=sk-your-api-key-here

# DeepSeek API 地址（可选，默认为官方地址）
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# LLM 模型（可选）
LLM_MODEL=deepseek-v4-pro

# 数据库路径（可选）
DATABASE_URL=sqlite:///./panel.db

# 使用 Mock 模式——跳过 API 调用，返回假数据（开发/测试用）
USE_MOCK_LLM=false
```

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `DEEPSEEK_API_KEY` | ✅ | — | DeepSeek API 密钥 |
| `DEEPSEEK_BASE_URL` | ❌ | `https://api.deepseek.com/v1` | API 基地址 |
| `LLM_MODEL` | ❌ | `deepseek-v4-pro` | 使用的模型名称 |
| `DATABASE_URL` | ❌ | `sqlite:///./panel.db` | SQLite 数据库路径 |
| `USE_MOCK_LLM` | ❌ | `false` | 设为 `true` 使用模拟 LLM（无需 API Key） |

---

## 运行指南

### 前提条件

- Python ≥3.11
- Node.js ≥20
- Git Bash 或其他 Unix Shell（Windows 平台）

### 后端启动

```bash
# 进入后端目录
cd backend

# 创建虚拟环境（首次）
python -m venv venv
source venv/Scripts/activate  # Windows Git Bash
# 或: venv\Scripts\activate   # Windows CMD

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY

# 启动（端口 8080）
python run.py
```

后端启动后可访问：
- API 文档（Swagger UI）：http://localhost:8080/docs
- 健康检查：http://localhost:8080/health

### 前端启动

```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 启动开发服务器（端口 5173）
npm run dev
```

前端启动后访问：http://localhost:5173

---

## 主要 API 列表

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/discussions` | 创建讨论 + LLM 生成阵容 |
| `GET` | `/api/discussions` | 获取讨论列表（支持分页和状态筛选） |
| `GET` | `/api/discussions/{id}` | 获取讨论详情（含发言/共识/分歧） |
| `POST` | `/api/discussions/{id}/start` | 确认阵容，开始讨论 |
| `POST` | `/api/discussions/{id}/end` | 结束讨论，生成主持总结 |
| `POST` | `/api/discussions/{id}/regenerate-roster` | 重新生成专家阵容 |
| `POST` | `/api/discussions/{id}/ask` | 向专家提问 |
| `GET` | `/api/discussions/{id}/stream` | SSE 实时事件流 |

完整 API 文档见：[docs/API.md](docs/API.md) 和启动后的 http://localhost:8080/docs

---

## 讨论生命周期

```
GENERATING → PENDING_CONFIRM → IN_PROGRESS → COMPLETED
   │              │                │
   └── LLM 生成    └── 用户确认      └── 用户结束/SSE summary
       阵容           阵容              触发
```

---

## 已完成能力

- ✅ LLM 生成多元立场专家阵容（1 主持人 + N 专家）
- ✅ 用户确认/重新生成阵容
- ✅ 异步专家自主发言循环（round-robin + 主持人串场）
- ✅ 实时 SSE 推送（speech / status_update / consensus_update / divergence_update / summary）
- ✅ 讨论过程中识别共识与分歧
- ✅ 主持人自然语言总结
- ✅ 用户可向专家定向提问
- ✅ Mock LLM 模式（无 API Key 也可运行）
- ✅ 完整的前端三栏讨论室 UI（专家列表 + 发言流 + 共识/分歧面板）
- ✅ 移动端适配（Tab 切换）
- ✅ SQLite 数据库 + 触发器（WAL 模式、外键约束）

---

## 后续改进方向

- [ ] 用户认证系统（注册/登录/JWT）
- [ ] 真正的 LLM 驱动的共识/分歧分析（当前为模拟实现）
- [ ] 讨论回放模式（已结束讨论的时间轴回放）
- [ ] Database 连接池与并发写入优化
- [ ] 前端状态管理与 SSE 重连指数退避
- [ ] 专家发言内容的多语言支持
- [ ] 讨论导出（PDF/Markdown）
- [ ] Docker 容器化部署
- [ ] 前端 E2E 测试
- [ ] WebSocket 升级（支持双向实时通信）
