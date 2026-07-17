# API 文档

> 版本 1.0 · 基于 OpenAPI 3.0 规范 · 完整规范见项目根目录 `api-spec.yaml`

**Base URL：** `http://localhost:8080/api`

**Content-Type：** `application/json`（REST 接口）；`text/event-stream`（SSE 接口）

---

## 一、通用约定

### 错误响应格式

所有错误响应遵循统一格式：

```json
{
  "detail": "Discussion not found"
}
```

HTTP 状态码：
- `400` — 参数校验失败或状态不允许
- `404` — 资源不存在
- `500` — 服务端错误（LLM 调用失败等）

---

## 二、讨论管理

### 2.1 创建讨论

```http
POST /api/discussions
```

**说明**：创建讨论记录，调用 LLM 生成 1 位主持人 + N 位专家的阵容，持久化后将状态设为 `PENDING_CONFIRM`。如果过程中任何一步失败，自动回滚删除已创建的数据。

**请求体：**

```json
{
  "topic": "人工智能是否应该拥有法律主体资格？",
  "expert_count": 3,
  "user_id": "550e8400-e29b-41d4-a716-446655440001"
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `topic` | string | ✅ | 讨论话题，1-500 字符 |
| `expert_count` | integer | ❌ | 专家人数（不含主持人），1-8，默认 4 |
| `user_id` | string | ❌ | 发起人 ID（UUID），默认使用内置用户 |

**成功响应 (201)：**

```json
{
  "discussion_id": "550e8400-e29b-41d4-a716-446655440100",
  "topic": "人工智能是否应该拥有法律主体资格？",
  "expert_count": 3,
  "status": "PENDING_CONFIRM",
  "roster": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440201",
      "name": "陈若溪",
      "role": "moderator",
      "profession": "科技媒体主编",
      "title": "《前沿对话》栏目首席主持人",
      "stance": "中立引导者",
      "color": "#6B7280"
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440202",
      "name": "林浩然",
      "role": "expert",
      "profession": "法学教授",
      "title": "北京大学法学院教授",
      "stance": "支持赋予AI有限法律主体资格",
      "color": "#3B82F6"
    }
  ]
}
```

**错误响应：**

| 状态码 | 说明 |
|--------|------|
| `400` | `topic` 为空 |
| `500` | LLM 阵容生成失败（此情况下讨论已被回滚删除） |

---

### 2.2 获取讨论列表

```http
GET /api/discussions?status=IN_PROGRESS&limit=20&offset=0
```

**查询参数：**

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `status` | string | ❌ | — | 按状态筛选：`GENERATING` / `PENDING_CONFIRM` / `IN_PROGRESS` / `COMPLETED` |
| `user_id` | string | ❌ | — | 按发起人筛选（UUID） |
| `limit` | integer | ❌ | 20 | 每页条数（1-100） |
| `offset` | integer | ❌ | 0 | 偏移量 |

**成功响应 (200)：**

```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440100",
      "topic": "人工智能是否应该拥有法律主体资格？",
      "status": "IN_PROGRESS",
      "expert_count": 3,
      "summary": null,
      "created_at": "2026-07-16T08:00:00Z"
    }
  ],
  "total": 1
}
```

---

### 2.3 获取讨论详情

```http
GET /api/discussions/{discussion_id}
```

**路径参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `discussion_id` | string (UUID) | 讨论 ID |

**成功响应 (200)：**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440100",
  "topic": "人工智能是否应该拥有法律主体资格？",
  "status": "IN_PROGRESS",
  "expert_count": 3,
  "summary": null,
  "started_at": "2026-07-16T08:10:00Z",
  "ended_at": null,
  "created_by": "550e8400-e29b-41d4-a716-446655440001",
  "created_at": "2026-07-16T08:00:00Z",
  "experts": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440201",
      "name": "陈若溪",
      "role": "moderator",
      "profession": "科技媒体主编",
      "title": "《前沿对话》栏目首席主持人",
      "stance": "中立引导者",
      "color": "#6B7280",
      "discussion_id": "..."
    }
  ],
  "transcripts": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440301",
      "content": "各位专家，欢迎来到今天的圆桌讨论...",
      "speaker_id": "550e8400-e29b-41d4-a716-446655440201",
      "discussion_id": "550e8400-e29b-41d4-a716-446655440100",
      "speech_type": "main",
      "reply_to_id": null,
      "created_at": "2026-07-16T08:10:01Z"
    }
  ],
  "consensus_list": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440401",
      "content": "各方一致认为现有法律框架存在责任归属灰色地带",
      "discussion_id": "550e8400-e29b-41d4-a716-446655440100",
      "source_transcript_ids": ["...440301", "...440302"],
      "updated_at": "2026-07-16T08:16:00Z"
    }
  ],
  "divergence_list": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440501",
      "content": "核心分歧：AI法律人格 vs. 纯人类责任框架",
      "discussion_id": "550e8400-e29b-41d4-a716-446655440100",
      "sides": [
        {
          "expert_id": "550e8400-e29b-41d4-a716-446655440202",
          "stance_label": "支持AI拟制人格",
          "summary": "借鉴公司法人制度，创设新型法律主体"
        }
      ],
      "source_transcript_ids": ["...440301", "...440303"],
      "updated_at": "2026-07-16T08:16:30Z"
    }
  ]
}
```

---

### 2.4 开始讨论

```http
POST /api/discussions/{discussion_id}/start
```

**说明**：确认阵容并启动讨论。要求当前状态为 `PENDING_CONFIRM`。成功后将状态转为 `IN_PROGRESS`，初始化 SSE 会话，启动异步发言引擎。

**路径参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `discussion_id` | string (UUID) | 讨论 ID |

**请求体（可选）：**

```json
{
  "confirmed_roster": [
    {
      "id": "...",
      "name": "林浩然",
      "role": "expert",
      "profession": "法学教授",
      "title": "北京大学法学院教授",
      "stance": "支持赋予AI有限法律主体资格",
      "color": "#3B82F6"
    }
  ]
}
```

> 若不传 `confirmed_roster`，则直接使用 LLM 生成的阵容。

**成功响应 (200)：**

```json
{
  "discussion_id": "550e8400-e29b-41d4-a716-446655440100",
  "status": "IN_PROGRESS",
  "started_at": "2026-07-16T08:10:00Z"
}
```

---

### 2.5 结束讨论

```http
POST /api/discussions/{discussion_id}/end
```

**说明**：结束讨论，触发主持人总结。要求当前状态为 `IN_PROGRESS`。调用 LLM 以主持人口吻生成自然语言总结，状态转为 `COMPLETED`，通过 SSE 广播 `summary` 事件后关闭流。

**成功响应 (200)：**

```json
{
  "discussion_id": "550e8400-e29b-41d4-a716-446655440100",
  "status": "COMPLETED",
  "summary": "经过近一小时的深入讨论，三位专家在AI法律人格问题上呈现了清晰的多元视角。林浩然教授主张借鉴公司法人制度创设AI拟制人格……苏婉清研究员则坚持人类不可推卸的最终责任……赵承宇从产业实践出发，提出风险分级可能比法律人格更加务实。我们的核心共识是：现有法律框架确实存在灰色地带，需要立法回应；而核心分歧在于回应的路径——是创设新主体还是完善现有追责链条。感谢各位的精彩发言。",
  "ended_at": "2026-07-16T09:00:00Z"
}
```

---

## 三、阵容操作

### 3.1 重新生成阵容

```http
POST /api/discussions/{discussion_id}/regenerate-roster
```

**说明**：重新调用 LLM 生成新的专家阵容。要求当前状态为 `PENDING_CONFIRM`。旧阵容将被删除。

**响应格式**：与 [2.1 创建讨论](#21-创建讨论) 相同。

---

## 四、用户提问

### 4.1 向专家提问

```http
POST /api/discussions/{discussion_id}/ask
```

**说明**：在讨论进行中向指定专家（或随机专家）提问。要求当前状态为 `IN_PROGRESS`。专家回答将作为 transcript 持久化并通过 SSE 广播。

**请求体：**

```json
{
  "question": "你认为这个议题对普通人最大的影响是什么？",
  "expert_id": "550e8400-e29b-41d4-a716-446655440202"
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `question` | string | ✅ | 提问内容，不可为空 |
| `expert_id` | string | ❌ | 目标专家 ID（UUID）。不传则随机选择一位专家 |

**成功响应 (200)：**

```json
{
  "status": "answered",
  "speech": {
    "id": "550e8400-e29b-41d4-a716-446655440305",
    "content": "关于这个问题，从法学教授的角度来看，我认为关键在于...",
    "speaker_id": "550e8400-e29b-41d4-a716-446655440202",
    "speaker_name": "林浩然",
    "speaker_color": "#3B82F6",
    "discussion_id": "550e8400-e29b-41d4-a716-446655440100",
    "speech_type": "main",
    "is_user_question": true,
    "created_at": "2026-07-16T08:25:00Z"
  }
}
```

---

## 五、SSE 实时事件流

### 5.1 订阅事件流

```http
GET /api/discussions/{discussion_id}/stream
```

**说明**：建立 SSE 长连接，接收讨论中产生的实时事件。客户端应使用浏览器原生 `EventSource` API。

**连接示例（JavaScript）：**

```javascript
const es = new EventSource(
  `http://localhost:8080/api/discussions/${discussionId}/stream`
);

es.addEventListener('speech', (e) => {
  const envelope = JSON.parse(e.data);
  console.log('新发言:', envelope.data.content);
});

es.addEventListener('summary', (e) => {
  const envelope = JSON.parse(e.data);
  console.log('讨论结束:', envelope.data.summary);
  es.close(); // 最后一条事件，关闭连接
});
```

### 5.2 事件类型

所有事件使用相同的 JSON 信封结构：

```json
{
  "event": "speech",
  "discussion_id": "550e8400-e29b-41d4-a716-446655440100",
  "timestamp": "2026-07-16T08:10:45Z",
  "data": { ... }
}
```

#### `speech` — 新发言

```json
{
  "event": "speech",
  "discussion_id": "...",
  "timestamp": "2026-07-16T08:10:45Z",
  "data": {
    "id": "...440302",
    "content": "我认为应当赋予AI有限的法律主体资格……",
    "speaker_id": "...440202",
    "speaker_name": "林浩然",
    "speaker_color": "#3B82F6",
    "discussion_id": "...",
    "speech_type": "main",
    "reply_to_id": null,
    "created_at": "2026-07-16T08:10:45Z"
  }
}
```

#### `status_update` — 状态变更

```json
{
  "event": "status_update",
  "discussion_id": "...",
  "timestamp": "2026-07-16T08:10:01Z",
  "data": {
    "discussion_id": "...",
    "previous_status": "PENDING_CONFIRM",
    "status": "IN_PROGRESS"
  }
}
```

#### `consensus_update` — 共识更新

```json
{
  "event": "consensus_update",
  "discussion_id": "...",
  "timestamp": "2026-07-16T08:16:00Z",
  "data": {
    "id": "...440401",
    "content": "各方一致认为现有法律框架存在责任归属灰色地带",
    "discussion_id": "...",
    "source_transcript_ids": ["...440302", "...440304"],
    "action": "created",
    "updated_at": "2026-07-16T08:16:00Z"
  }
}
```

| `action` 值 | 含义 |
|-------------|------|
| `created` | 新共识产生 |
| `updated` | 既有共识内容被更新 |

#### `divergence_update` — 分歧更新

```json
{
  "event": "divergence_update",
  "discussion_id": "...",
  "timestamp": "2026-07-16T08:16:30Z",
  "data": {
    "id": "...440501",
    "content": "核心分歧：AI法律人格 vs. 纯人类责任框架",
    "discussion_id": "...",
    "sides": [
      {
        "expert_id": "...440202",
        "stance_label": "支持AI拟制人格",
        "summary": "借鉴公司法人制度，创设新型法律主体"
      }
    ],
    "source_transcript_ids": ["...440302", "...440303"],
    "action": "created",
    "updated_at": "2026-07-16T08:16:30Z"
  }
}
```

#### `summary` — 讨论结束总结（最终事件）

> ⚠️ 收到此事件后，SSE 流将由服务端关闭，客户端无需重连。

```json
{
  "event": "summary",
  "discussion_id": "...",
  "timestamp": "2026-07-16T09:00:00Z",
  "data": {
    "discussion_id": "...",
    "summary": "经过近一小时的深入讨论……",
    "ended_at": "2026-07-16T09:00:00Z"
  }
}
```

### 5.3 事件流生命周期

```
客户端连接
    │
    ├── SSE: speech (N 次，按 round-robin 轮流)
    ├── SSE: status_update（讨论状态变更 / 专家 typing/speaking/idle）
    ├── SSE: consensus_update（每 ANALYSIS_INTERVAL 轮分析）
    ├── SSE: divergence_update（每 ANALYSIS_INTERVAL 轮分析）
    │
    └── SSE: summary（讨论结束，服务端关闭连接）
```

### 5.4 重连策略

SSE 连接意外断开时，前端应使用指数退避重连：

| 尝试次数 | 延迟 |
|----------|------|
| 1 | 1s |
| 2 | 2s |
| 3 | 4s |
| 4 | 8s |
| 5+ | 30s（上限） |

如果收到的最后一条事件是 `summary`，说明讨论已正常结束，无需重连。

---

## 六、数据字典

### DiscussionStatus

| 值 | 说明 |
|----|------|
| `GENERATING` | LLM 正在生成阵容（中间状态，用户不可操作） |
| `PENDING_CONFIRM` | 阵容已生成，等待用户确认 |
| `IN_PROGRESS` | 讨论进行中 |
| `COMPLETED` | 讨论已结束 |

### ExpertRole

| 值 | 说明 |
|----|------|
| `moderator` | 主持人——引导讨论、串场、做总结 |
| `expert` | 专家——持特定立场参与辩论 |

### SpeechType

| 值 | 说明 |
|----|------|
| `main` | 主发言——提出新观点或独立论述 |
| `supplement` | 补充——在前人观点基础上延伸 |
| `rebuttal` | 反驳——不同意前人观点，提出反对意见 |
| `question` | 提问——向其他专家提出问题 |
