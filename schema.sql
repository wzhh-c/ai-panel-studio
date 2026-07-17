-- ============================================================
-- 圆桌讨论系统 — SQLite DDL
-- 基于领域模型 v1.0
-- ============================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ============================================================
-- 1. User（用户）
-- ============================================================
CREATE TABLE IF NOT EXISTS "user" (
    id         TEXT NOT NULL PRIMARY KEY,               -- UUID v4
    name       TEXT NOT NULL,                            -- 用户昵称
    created_at TEXT NOT NULL DEFAULT (datetime('now')),  -- 注册时间
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- 2. Discussion（讨论）
-- ============================================================
CREATE TABLE IF NOT EXISTS discussion (
    id           TEXT NOT NULL PRIMARY KEY,               -- UUID v4
    topic        TEXT NOT NULL,                            -- 讨论话题
    expert_count INTEGER NOT NULL DEFAULT 4,               -- 专家人数 N（含主持人）
    status       TEXT NOT NULL DEFAULT 'GENERATING'        -- 生命周期
                     CHECK (status IN (
                         'GENERATING',
                         'PENDING_CONFIRM',
                         'IN_PROGRESS',
                         'COMPLETED'
                     )),
    summary      TEXT,                                     -- 主持人总结（COMPLETED 后填充）
    started_at   TEXT,                                     -- 讨论开始时间
    ended_at     TEXT,                                     -- 讨论结束时间
    created_by   TEXT NOT NULL,                            -- FK → user.id
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (created_by) REFERENCES "user"(id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

-- ============================================================
-- 3. Expert（专家 / 主持人）
-- ============================================================
CREATE TABLE IF NOT EXISTS expert (
    id            TEXT NOT NULL PRIMARY KEY,               -- UUID v4
    name          TEXT NOT NULL,                            -- 专家姓名（大模型生成）
    role          TEXT NOT NULL DEFAULT 'expert'            -- 角色
                      CHECK (role IN ('moderator', 'expert')),
    profession    TEXT NOT NULL,                            -- 职业
    title         TEXT NOT NULL,                            -- 头衔 / 称谓
    stance        TEXT NOT NULL,                            -- 立场描述
    color         TEXT NOT NULL,                            -- 代表色 hex，如 #3B82F6
    discussion_id TEXT NOT NULL,                            -- FK → discussion.id
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (discussion_id) REFERENCES discussion(id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

-- 业务规则：每个 discussion 只有一个 moderator
CREATE UNIQUE INDEX idx_expert_moderator_unique
    ON expert(discussion_id) WHERE role = 'moderator';

CREATE INDEX idx_expert_discussion ON expert(discussion_id);

-- ============================================================
-- 4. Transcript（发言记录）
-- ============================================================
CREATE TABLE IF NOT EXISTS transcript (
    id            TEXT NOT NULL PRIMARY KEY,               -- UUID v4
    content       TEXT NOT NULL CHECK (length(content) > 0), -- 发言原文（不可为空）
    speaker_id    TEXT NOT NULL,                            -- FK → expert.id
    discussion_id TEXT NOT NULL,                            -- FK → discussion.id
    speech_type   TEXT NOT NULL DEFAULT 'main'              -- 发言类型
                      CHECK (speech_type IN (
                          'main',
                          'supplement',
                          'rebuttal',
                          'question'
                      )),
    reply_to_id   TEXT,                                     -- FK → transcript.id（反驳/补充时必填）
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (speaker_id)    REFERENCES expert(id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (discussion_id) REFERENCES discussion(id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (reply_to_id)   REFERENCES transcript(id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    -- 业务规则：反驳/补充时必须指定回复目标
    CHECK (
        (speech_type IN ('supplement', 'rebuttal') AND reply_to_id IS NOT NULL)
        OR
        (speech_type IN ('main', 'question'))
    )
);

CREATE INDEX idx_transcript_discussion ON transcript(discussion_id);
CREATE INDEX idx_transcript_speaker    ON transcript(speaker_id);
CREATE INDEX idx_transcript_reply_to   ON transcript(reply_to_id);

-- ============================================================
-- 5. Consensus（共识）
-- ============================================================
CREATE TABLE IF NOT EXISTS consensus (
    id                    TEXT NOT NULL PRIMARY KEY,       -- UUID v4
    content               TEXT NOT NULL CHECK (length(content) > 0), -- 共识内容（不可为空）
    discussion_id         TEXT NOT NULL,                    -- FK → discussion.id
    source_transcript_ids TEXT NOT NULL,                    -- JSON 数组，至少 2 条引用
    created_at            TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at            TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (discussion_id) REFERENCES discussion(id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CHECK (json_array_length(source_transcript_ids) >= 2)
);

CREATE INDEX idx_consensus_discussion ON consensus(discussion_id);

-- ============================================================
-- 6. Divergence（分歧）
-- ============================================================
CREATE TABLE IF NOT EXISTS divergence (
    id                    TEXT NOT NULL PRIMARY KEY,       -- UUID v4
    content               TEXT NOT NULL CHECK (length(content) > 0), -- 分歧点描述（不可为空）
    discussion_id         TEXT NOT NULL,                    -- FK → discussion.id
    sides                 TEXT NOT NULL,                    -- JSON: [{expert_id, stance_label, summary}]
    source_transcript_ids TEXT NOT NULL,                    -- JSON 数组，至少 2 条引用
    created_at            TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at            TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (discussion_id) REFERENCES discussion(id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CHECK (json_array_length(source_transcript_ids) >= 2),
    CHECK (json_array_length(sides) >= 2)
);

CREATE INDEX idx_divergence_discussion ON divergence(discussion_id);

-- ============================================================
-- 7. 触发器：updated_at 自动更新
-- ============================================================
CREATE TRIGGER trg_user_updated_at AFTER UPDATE ON "user"
BEGIN
    UPDATE "user" SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER trg_discussion_updated_at AFTER UPDATE ON discussion
BEGIN
    UPDATE discussion SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER trg_expert_updated_at AFTER UPDATE ON expert
BEGIN
    UPDATE expert SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER trg_transcript_updated_at AFTER UPDATE ON transcript
BEGIN
    UPDATE transcript SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER trg_consensus_updated_at AFTER UPDATE ON consensus
BEGIN
    UPDATE consensus SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER trg_divergence_updated_at AFTER UPDATE ON divergence
BEGIN
    UPDATE divergence SET updated_at = datetime('now') WHERE id = NEW.id;
END;

-- ============================================================
-- 8. 触发器：讨论进入 COMPLETED 后阻止新增发言
-- ============================================================
CREATE TRIGGER trg_transcript_insert_guard BEFORE INSERT ON transcript
FOR EACH ROW
BEGIN
    SELECT CASE
        WHEN (SELECT status FROM discussion WHERE id = NEW.discussion_id) = 'COMPLETED'
        THEN RAISE(ABORT, '讨论已结束，不允许新增发言')
    END;
END;
