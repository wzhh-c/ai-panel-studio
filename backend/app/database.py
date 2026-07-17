"""SQLite 数据库连接管理。

提供连接上下文管理器、初始化函数。
"""

import sqlite3
import os
from contextlib import contextmanager
from pathlib import Path

# 数据库文件路径 — 项目根目录下的 panel.db
DB_PATH = Path(__file__).resolve().parent.parent / "panel.db"


@contextmanager
def get_db_connection() -> sqlite3.Connection:
    """获取 SQLite 数据库连接（上下文管理器）。

    每次调用返回一个新连接，启用外键约束和 WAL 模式。
    row_factory 设为 sqlite3.Row，支持字典式列访问。
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """初始化数据库。

    1. 读取 docs/schema.sql 并执行建表（IF NOT EXISTS 保证幂等）。
    2. 插入 2 条样例用户数据（幂等）。
    """
    schema_path = Path(__file__).resolve().parent.parent / "docs" / "schema.sql"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema 文件不存在: {schema_path}")

    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    with get_db_connection() as conn:
        # 执行 DDL 脚本
        conn.executescript(schema_sql)

        # 幂等插入 2 条样例用户
        conn.execute(
            """
            INSERT OR IGNORE INTO "user" (id, name) VALUES (?, ?)
            """,
            ("550e8400-e29b-41d4-a716-446655440001", "张明远"),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO "user" (id, name) VALUES (?, ?)
            """,
            ("550e8400-e29b-41d4-a716-446655440002", "李思涵"),
        )
