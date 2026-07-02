import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings

DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{settings.DATABASE_PATH}")

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL, pool_size=20, max_overflow=30, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Import all models so they register with Base.metadata
import services.models  # noqa: F401, E402


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _migrate_add_cols(table: str, cols_to_add: dict[str, str]):
    from sqlalchemy import inspect as _inspect
    inspector = _inspect(engine)
    try:
        existing = {c["name"] for c in inspector.get_columns(table)}
    except Exception:
        return
    with engine.connect() as conn:
        for col_name, col_def in cols_to_add.items():
            if col_name not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}"))
        conn.commit()


def _is_sqlite():
    return DATABASE_URL.startswith("sqlite")

def init_db():
    # Ensure data subdirectories exist (bind mount may not have them on fresh start)
    os.makedirs(os.path.join(os.path.dirname(settings.DATABASE_PATH), "reports"), exist_ok=True)

    if _is_sqlite():
        db_file = settings.DATABASE_PATH
        was_empty = not os.path.exists(db_file) or os.path.getsize(db_file) < 4096
    else:
        was_empty = False

    Base.metadata.create_all(bind=engine)

    if _is_sqlite():
        # Warn if DB was newly created on a volume that should have existing data
        if was_empty:
            from sqlalchemy import inspect
            insp = inspect(engine)
            with engine.connect() as conn:
                row_count = conn.execute(text("SELECT COUNT(*) FROM knowledge_base")).scalar()
            if row_count == 0:
                logger = logging.getLogger(__name__)
                logger.warning(
                    "数据库为空！检查数据卷是否挂载正确。"
                    " 预期路径: %s (宿主机: %s)",
                    db_file,
                    os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "app.db"),
                )
                logger.warning(
                    "如果数据丢失，可以从宿主机 %s/data/app.db 恢复",
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                )
        from sqlalchemy import inspect
        inspector = inspect(engine)

        # SQLite-specific ALTER TABLE migrations (PostgreSQL uses Alembic/create_all)
        cols = [c["name"] for c in inspector.get_columns("crawled_jobs")]
        if "jd_parsed" not in cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE crawled_jobs ADD COLUMN jd_parsed TEXT DEFAULT ''"))
                conn.commit()
        if "work_address" not in cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE crawled_jobs ADD COLUMN work_address TEXT DEFAULT ''"))
                conn.commit()

        try:
            cols = [c["name"] for c in inspector.get_columns("interview_guides")]
            if "session_id" not in cols:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE interview_guides ADD COLUMN session_id TEXT"))
                    conn.commit()
        except Exception:
            pass

        try:
            pc_cols = {c["name"] for c in inspector.get_columns("portfolio_configs")}
            if "user_id" in pc_cols and "id" in pc_cols:
                _migrate_portfolio_config()
        except Exception:
            pass

        try:
            pt_cols = {c["name"] for c in inspector.get_columns("portfolio_contents")}
            if "user_id" in pt_cols and "id" in pt_cols:
                _migrate_portfolio_contents()
        except Exception:
            pass

    # Apply migrations for all database types (SQLite and PostgreSQL)
    _migrate_add_cols("agent_conversations", {
        "user_id": "VARCHAR DEFAULT ''",
        "resume_id": "INTEGER",
    })
    _migrate_add_cols("agent_events", {
        "user_id": "VARCHAR DEFAULT ''",
    })
    _migrate_add_cols("report_generation_tasks", {
        "progress_message": "VARCHAR DEFAULT ''",
    })


def _migrate_portfolio_config():
    """Rebuild portfolio_configs with user_id as PK."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE portfolio_configs_new (
                user_id VARCHAR PRIMARY KEY,
                style TEXT DEFAULT 'editorial',
                blocks_order TEXT DEFAULT '["hero", "about", "experience", "projects", "contact"]',
                blocks_hidden TEXT DEFAULT '[]',
                contact_enabled TEXT DEFAULT '{"email": true, "phone": true, "github": true, "wechat": false}',
                chat_enabled INTEGER DEFAULT 0,
                chat_position TEXT DEFAULT 'bottom-right',
                portfolio_show INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            INSERT INTO portfolio_configs_new (user_id, style, blocks_order, blocks_hidden,
                contact_enabled, chat_enabled, chat_position, portfolio_show, updated_at)
            SELECT '', style, blocks_order, blocks_hidden,
                contact_enabled, chat_enabled, chat_position, portfolio_show, updated_at
            FROM portfolio_configs
        """))
        conn.execute(text("DROP TABLE portfolio_configs"))
        conn.execute(text("ALTER TABLE portfolio_configs_new RENAME TO portfolio_configs"))
        conn.commit()


def _migrate_portfolio_contents():
    """Rebuild portfolio_contents with user_id as PK."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE portfolio_contents_new (
                user_id VARCHAR PRIMARY KEY,
                content_json TEXT DEFAULT '{}',
                built_at TIMESTAMP
            )
        """))
        conn.execute(text("""
            INSERT INTO portfolio_contents_new (user_id, content_json, built_at)
            SELECT '', content_json, built_at FROM portfolio_contents
        """))
        conn.execute(text("DROP TABLE portfolio_contents"))
        conn.execute(text("ALTER TABLE portfolio_contents_new RENAME TO portfolio_contents"))
        conn.commit()
