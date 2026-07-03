"""
单用户 → 多租户数据迁移脚本。
在你服务器上手动跑一次，不包含在开源代码中。

用法:
  python scripts/migrate_single_to_multi.py

作用:
  1. 创建 users / user_configs / system_configs / llm_usage 表（如果不存在）
  2. 将 .env 中的 admin 账号导入 users 表
  3. 将所有旧数据（user_id = ''）绑定到 admin 用户
"""

import os
import sys
import uuid
import bcrypt
import json
import shutil
from datetime import datetime

# ── 路径 ─────────────────────────────────────────────
BACKEND_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "hr-agent", "backend"))
DB_PATH = os.path.join(BACKEND_DIR, "data", "app.db")
ENV_PATH = os.path.join(BACKEND_DIR, "..", ".env")

# 也检查挂载的 data 路径
DATA_DIR = os.path.join(BACKEND_DIR, "..", "data")
DATA_DB_PATH = os.path.join(DATA_DIR, "app.db")


def load_env():
    """Simple .env parser — read ADMIN_USERNAME / ADMIN_PASSWORD"""
    env_vars = {}
    env_file = ENV_PATH
    if not os.path.exists(env_file):
        env_file = os.path.join(BACKEND_DIR, ".env")
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip()
    return env_vars


def get_db_path():
    """Find the actual DB file — check data/ first, then backend/data/"""
    for p in [DATA_DB_PATH, DB_PATH]:
        if os.path.exists(p):
            return p
    # Default to data/ mount path
    os.makedirs(DATA_DIR, exist_ok=True)
    return DATA_DB_PATH


def migrate():
    import sqlite3

    db_path = get_db_path()
    print(f"数据库路径: {db_path}")
    print(f"存在: {os.path.exists(db_path)}")

    # 1. 备份
    bak_path = db_path + ".bak"
    if not os.path.exists(bak_path):
        shutil.copy2(db_path, bak_path)
        print(f"✓ 已备份到 {bak_path}")
    else:
        print(f"! 备份已存在，跳过: {bak_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    # 2. 检查是否已有 users 表
    existing = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
    ).fetchone()

    if existing:
        print("✓ users 表已存在")
    else:
        # 创建新表
        conn.executescript("""
            CREATE TABLE users (
                id VARCHAR PRIMARY KEY,
                username VARCHAR UNIQUE NOT NULL,
                email VARCHAR UNIQUE NOT NULL,
                password_hash VARCHAR NOT NULL,
                role VARCHAR DEFAULT 'user',
                is_active BOOLEAN DEFAULT TRUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE user_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id VARCHAR NOT NULL REFERENCES users(id),
                config_key VARCHAR NOT NULL,
                config_value TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, config_key)
            );
            CREATE TABLE system_configs (
                key VARCHAR PRIMARY KEY,
                value TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE llm_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id VARCHAR NOT NULL,
                event_type VARCHAR NOT NULL,
                model VARCHAR DEFAULT '',
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                search_calls INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX idx_llm_usage_user ON llm_usage(user_id);
            CREATE INDEX idx_llm_usage_user_date ON llm_usage(user_id, created_at);
        """)
        print("✓ 已创建 users / user_configs / system_configs / llm_usage 表")

    # 3. 从 .env 读取 admin 账号
    env = load_env()
    admin_username = env.get("ADMIN_USERNAME", "admin")
    admin_password = env.get("ADMIN_PASSWORD", "admin123")
    admin_email = env.get("ADMIN_EMAIL", "admin@local")

    # 检查 admin 是否已存在
    existing_admin = conn.execute(
        "SELECT id, username FROM users WHERE username = ?", (admin_username,)
    ).fetchone()

    if existing_admin:
        admin_id = existing_admin["id"]
        print(f"✓ admin 用户已存在: {existing_admin['username']} (id={admin_id})")
    else:
        admin_id = str(uuid.uuid4())
        hashed = bcrypt.hashpw(admin_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        conn.execute(
            "INSERT INTO users (id, username, email, password_hash, role) VALUES (?, ?, ?, ?, ?)",
            (admin_id, admin_username, admin_email, hashed, "super_admin"),
        )
        print(f"✓ 已创建 admin 用户: {admin_username} (id={admin_id})")

    # 4. 迁移旧数据 — 将 user_id = '' 或 NULL 的记录更新为 admin_id
    tables_to_migrate = [
        ("knowledge_base", "user_id"),
        ("stats", "user_id"),
        ("sessions", "user_id"),
        ("portfolio_configs", "user_id"),
        ("portfolio_contents", "user_id"),
        ("resumes", "user_id"),
        ("applicant_profile", "user_id"),
        ("crawled_jobs", "user_id"),
        ("interview_guides", "user_id"),
        ("agent_conversations", "user_id"),
    ]

    total_updated = 0
    for table, col in tables_to_migrate:
        # 检查表是否存在
        tbl = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if not tbl:
            continue

        # 检查列是否存在
        cols = [c[1] for c in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if col not in cols:
            print(f"  ! {table} 没有 {col} 列，跳过")
            continue

        # 更新空 user_id 为 admin_id
        cur = conn.execute(
            f"UPDATE {table} SET {col}=? WHERE {col} IS NULL OR {col}=''",
            (admin_id,),
        )
        if cur.rowcount > 0:
            total_updated += cur.rowcount
            print(f"  ✓ {table}: 更新 {cur.rowcount} 条记录")

    # 5. 检查并更新 conversation 表（可能通过 session 关联）
    tbl = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='conversations'"
    ).fetchone()
    if tbl:
        cols = [c[1] for c in conn.execute("PRAGMA table_info(conversations)").fetchall()]
        if "user_id" in cols:
            cur = conn.execute(
                "UPDATE conversations SET user_id=? WHERE user_id IS NULL OR user_id=''",
                (admin_id,),
            )
            if cur.rowcount > 0:
                total_updated += cur.rowcount
                print(f"  ✓ conversations: 更新 {cur.rowcount} 条记录")

    # 6. 将 admin 用户同步到 user_configs 表（访客口令等）
    if not conn.execute(
        "SELECT 1 FROM user_configs WHERE user_id=? AND config_key='visitor_password'",
        (admin_id,),
    ).fetchone():
        visitor_pw = env.get("VISITOR_PASSWORD", "AGENTAGENT")
        conn.execute(
            "INSERT INTO user_configs (user_id, config_key, config_value) VALUES (?, 'visitor_password', ?)",
            (admin_id, visitor_pw),
        )
        print(f"  ✓ 已创建 admin 的访客口令配置")

    conn.commit()
    conn.close()

    print(f"\n✅ 迁移完成！共更新 {total_updated} 条记录")
    print(f"   admin 用户: {admin_username} / {admin_password}")
    print(f"   admin UUID: {admin_id}")
    print(f"\n   其他用户注册后数据独立，不会看到 admin 的数据。")


if __name__ == "__main__":
    migrate()
