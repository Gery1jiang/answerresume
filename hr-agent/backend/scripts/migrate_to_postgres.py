"""SQLite → PostgreSQL 数据迁移脚本。

用法：
  DATABASE_URL=postgresql://gery:answeragent2026@localhost:5432/answeragent \
  python scripts/migrate_to_postgres.py
"""

import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migrate")

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker


# Tables with FK dependencies must come after their referenced tables
TABLE_ORDER = [
    "users",
    "sessions",
    "user_configs",
    "system_configs",
    "knowledge_base",
    "agent_tasks",
    "agent_conversations",
    "agent_events",
    "conversations",
    "crawled_jobs",
    "applicant_profile",
    "interview_guides",
    "resumes",
    "llm_usage",
    "portfolio_configs",
    "portfolio_contents",
    "prompt_templates",
    "prompt_versions",
    "report_generation_tasks",
    "stats",
]

SKIP_TABLES = {"alembic_version"}


def migrate():
    from config import settings
    sqlite_url = f"sqlite:///{settings.DATABASE_PATH}"
    logger.info("Source: %s", sqlite_url)
    sqlite_engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
    SQLiteSession = sessionmaker(bind=sqlite_engine)

    pg_url = os.environ.get("DATABASE_URL", "").strip()
    if not pg_url:
        raise ValueError("DATABASE_URL env var required")
    logger.info("Target: %s", pg_url.split("@")[-1] if "@" in pg_url else pg_url)
    pg_engine = create_engine(pg_url)
    PGSession = sessionmaker(bind=pg_engine)

    from services.database import Base
    import services.models  # noqa: F401

    logger.info("Creating tables in PostgreSQL...")
    Base.metadata.create_all(bind=pg_engine)

    inspector = inspect(sqlite_engine)
    sqlite_tables = set(inspector.get_table_names()) - SKIP_TABLES

    model_map = {}
    for mapper in Base.registry.mappers:
        table_name = mapper.persist_selectable.name
        model_map[table_name] = mapper.entity

    # Disable FK checks in PostgreSQL for clean migration
    pg_db = PGSession()
    pg_db.execute(text("SET session_replication_role = 'replica';"))
    pg_db.commit()

    total_rows = 0
    copied_tables = 0

    for table_name in TABLE_ORDER:
        if table_name not in sqlite_tables or table_name not in model_map:
            continue

        cls = model_map[table_name]
        columns = [c.name for c in cls.__table__.columns]

        sqlite_db = SQLiteSession()
        rows = sqlite_db.query(cls).all()
        sqlite_db.close()

        if not rows:
            logger.info("  %s: 0 rows (empty)", table_name)
            continue

        try:
            for row in rows:
                data = {c: getattr(row, c) for c in columns}
                pg_db.execute(cls.__table__.insert().values(**data))
            pg_db.commit()
            logger.info("  %s: %d rows copied", table_name, len(rows))
            total_rows += len(rows)
            copied_tables += 1
        except Exception as e:
            pg_db.rollback()
            logger.warning("  %s FAILED (skipping): %s", table_name, e)

    # Also copy any tables not in TABLE_ORDER
    ordered_set = set(TABLE_ORDER)
    for table_name in sqlite_tables:
        if table_name in ordered_set or table_name not in model_map:
            continue
        cls = model_map[table_name]
        columns = [c.name for c in cls.__table__.columns]
        sqlite_db = SQLiteSession()
        rows = sqlite_db.query(cls).all()
        sqlite_db.close()
        if not rows:
            continue
        try:
            for row in rows:
                data = {c: getattr(row, c) for c in columns}
                pg_db.execute(cls.__table__.insert().values(**data))
            pg_db.commit()
            logger.info("  %s: %d rows copied", table_name, len(rows))
            total_rows += len(rows)
            copied_tables += 1
        except Exception as e:
            pg_db.rollback()
            logger.warning("  %s FAILED (skipping): %s", table_name, e)

    # Re-enable FK checks
    pg_db.execute(text("SET session_replication_role = 'origin';"))
    pg_db.commit()

    # Update sequences (only for integer PKs)
    for table_name in sqlite_tables:
        if table_name not in model_map:
            continue
        cls = model_map[table_name]
        for col in cls.__table__.columns:
            if col.autoincrement and col.primary_key:
                col_type = str(col.type)
                if "INT" not in col_type.upper():
                    continue  # skip UUID/text PKs
                seq_name = f"{table_name}_{col.name}_seq"
                try:
                    result = pg_db.execute(text(f"SELECT setval('{seq_name}', (SELECT MAX({col.name}) FROM {table_name}))"))
                    logger.info("  Sequence %s set to %s", seq_name, result.scalar())
                except Exception as e:
                    logger.warning("  Sequence %s update failed: %s", seq_name, e)
    pg_db.commit()
    pg_db.close()

    logger.info("Migration complete: %d rows across %d tables.", total_rows, copied_tables)


if __name__ == "__main__":
    migrate()
