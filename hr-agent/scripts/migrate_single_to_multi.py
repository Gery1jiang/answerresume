"""
Single-user → Multi-tenant migration script.

WARNING: This is a ONE-TIME manual migration script, NOT part of application code.
It must be executed once when upgrading from single-user to multi-tenant.

Usage:
    cd /path/to/project
    python scripts/migrate_single_to_multi.py

What it does:
  1. Creates super_admin user (admin / admin123) if not exists
  2. Sets user_id = admin.id on all existing data rows
  3. Rebuilds unique constraints (knowledge_base, resumes)
  4. Migrates applicant_profile (id=1 → user_id PK)
  5. Migrates portfolio tables (id → user_id PK)
  6. Creates default UserConfig for the admin
"""

import os
import sys
import json
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "app.db")
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_engine():
    db_url = os.environ.get("DATABASE_URL", f"sqlite:///{DB_PATH}")
    return create_engine(db_url, echo=False)


def ensure_super_admin(db):
    result = db.execute(
        text("SELECT id, role FROM users WHERE username = :un"),
        {"un": ADMIN_USERNAME},
    ).fetchone()

    if result:
        print(f"[OK] Admin user '{ADMIN_USERNAME}' already exists (id={result[0]})")
        return result[0], result[1] == "super_admin"

    hashed = pwd_context.hash(ADMIN_PASSWORD)
    now = datetime.utcnow().isoformat()
    db.execute(
        text("INSERT INTO users (username, hashed_password, role, is_active, created_at, updated_at) "
             "VALUES (:un, :pw, :role, 1, :now, :now)"),
        {"un": ADMIN_USERNAME, "pw": hashed, "role": "super_admin", "now": now},
    )
    db.commit()
    result = db.execute(
        text("SELECT id, role FROM users WHERE username = :un"),
        {"un": ADMIN_USERNAME},
    ).fetchone()
    print(f"[CREATED] Super admin user id={result[0]}")
    return result[0], True


def set_user_id(db, table, admin_id):
    result = db.execute(
        text(f"UPDATE {table} SET user_id = :uid "
             f"WHERE user_id IS NULL OR user_id = '' OR user_id = '0'"),
        {"uid": str(admin_id)},
    )
    count = result.rowcount
    if count > 0:
        print(f"  [MIGRATED] {table}: {count} rows updated")
    else:
        print(f"  [SKIP] {table}: no rows needed migration")
    db.commit()


def migrate(db, admin_id):
    """Set user_id on all tables that have the column."""
    for table in [
        "resumes", "agent_conversations", "sessions", "conversations",
        "knowledge_base", "interview_guides", "crawled_jobs", "stats",
        "applicant_profile", "portfolio_config", "portfolio_content",
        "report_generation_tasks",
    ]:
        try:
            db.execute(text(f"SELECT user_id FROM {table} LIMIT 1"))
            set_user_id(db, table, admin_id)
        except Exception:
            print(f"  [SKIP] {table}: no user_id column (may not exist yet)")


def rebuild_unique_constraints(db, engine, admin_id):
    """
    SQLite cannot ALTER unique constraints.
    For tables with (user_id + field) uniqueness, this ensures it's correct.
    """
    from sqlalchemy import inspect

    rebuilds = {
        "knowledge_base": {
            "create": (
                "CREATE TABLE IF NOT EXISTS knowledge_base_new ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "user_id TEXT DEFAULT '', "
                "category TEXT, "
                "data TEXT, "
                "UNIQUE(user_id, category)"
                ")"
            ),
            "insert": "INSERT OR IGNORE INTO knowledge_base_new SELECT * FROM knowledge_base",
            "old_cols": ["id", "user_id", "category", "data"],
        },
        "resumes": {
            "create": (
                "CREATE TABLE IF NOT EXISTS resumes_new ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "user_id TEXT DEFAULT '', "
                "filename TEXT, "
                "title TEXT, "
                "content TEXT, "
                "is_default BOOLEAN, "
                "created_at TIMESTAMP, "
                "UNIQUE(user_id, filename)"
                ")"
            ),
            "insert": "INSERT OR IGNORE INTO resumes_new SELECT * FROM resumes",
            "old_cols": ["id", "user_id", "filename", "title", "content", "is_default", "created_at"],
        },
    }

    for table, spec in rebuilds.items():
        inspector = inspect(engine)
        try:
            indexes = inspector.get_indexes(table)
            uniq_indices = [i for i in indexes if i.get("unique") or (i.get("name") and "unique" in i["name"].lower())]
            cols_in_uniq = set()
            for idx in uniq_indices:
                cols_in_uniq.update(idx.get("column_names", []))
            if "user_id" in cols_in_uniq:
                print(f"  [OK] {table} already has user_id in unique constraint")
                continue
        except Exception:
            pass

        print(f"  [REBUILD] Rebuilding {table} with (user_id, field) unique constraint...")
        try:
            new_table = f"{table}_new"
            old_backup = f"{table}_old_{int(datetime.utcnow().timestamp())}"

            db.execute(text(spec["create"]))
            db.execute(text(spec["insert"]))
            db.execute(text(f"ALTER TABLE {table} RENAME TO {old_backup}"))
            db.execute(text(f"ALTER TABLE {new_table} RENAME TO {table}"))
            db.commit()
            print(f"  -> Done. Old table backed up as {old_backup}")
        except Exception as e:
            db.rollback()
            print(f"  [WARN] Could not rebuild {table}: {e}")


def ensure_applicant_profile(db, admin_id):
    row = db.execute(
        text("SELECT user_id FROM applicant_profile WHERE id = 1")
    ).fetchone()

    if row:
        uid = row[0]
        if uid and str(uid).strip() and str(uid) != "0":
            print(f"  [OK] applicant_profile already has user_id={uid}")
            return
        db.execute(
            text("UPDATE applicant_profile SET user_id = :uid WHERE id = 1"),
            {"uid": str(admin_id)},
        )
        db.commit()
        print(f"  [MIGRATED] applicant_profile: set user_id={admin_id}")
    else:
        print(f"  [SKIP] applicant_profile: no rows")


def ensure_portfolio_tables(db, admin_id):
    for table in ["portfolio_config", "portfolio_content"]:
        rows = db.execute(text(f"SELECT id, user_id FROM {table}")).fetchall()
        updated = 0
        for row in rows:
            uid = row[1]
            if uid and str(uid).strip() and str(uid) != "0":
                continue
            db.execute(
                text(f"UPDATE {table} SET user_id = :uid WHERE id = :rid"),
                {"uid": str(admin_id), "rid": row[0]},
            )
            updated += 1
        if updated > 0:
            print(f"  [MIGRATED] {table}: {updated} rows updated")
        else:
            print(f"  [SKIP] {table}: no rows")
    db.commit()


def ensure_user_config(db, admin_id):
    row = db.execute(
        text("SELECT id FROM user_config WHERE user_id = :uid"),
        {"uid": str(admin_id)},
    ).fetchone()

    if row:
        print(f"[OK] UserConfig for admin already exists")
        return

    db.execute(
        text("INSERT INTO user_config (user_id, visitor_enabled, visitor_password) "
             "VALUES (:uid, 0, '')"),
        {"uid": str(admin_id)},
    )
    db.commit()
    print(f"[CREATED] Default UserConfig for admin")


def copy_knowledge_to_user_dir(admin_id):
    """Copy global knowledge/ directory to user_data/{admin_id}/knowledge/."""
    global_kb = os.path.join(os.path.dirname(__file__), "..", "backend", "knowledge")
    user_kb = os.path.join(os.path.dirname(__file__), "..", "backend", "user_data", str(admin_id), "knowledge")
    
    if not os.path.isdir(global_kb):
        print("[SKIP] No global knowledge directory found")
        return
    
    if os.path.isdir(user_kb):
        print(f"[OK] User knowledge dir already exists: {user_kb}")
        return
    
    import shutil
    os.makedirs(os.path.dirname(user_kb), exist_ok=True)
    shutil.copytree(global_kb, user_kb, dirs_exist_ok=True)
    print(f"[COPIED] Global knowledge → {user_kb} ({len(os.listdir(user_kb))} files)")


def main():
    print("=" * 60)
    print("  Single-User to Multi-Tenant Migration")
    print("=" * 60)

    if not os.path.exists(DB_PATH):
        print(f"[ERROR] Database not found: {DB_PATH}")
        print("Run this from the project root directory.")
        sys.exit(1)

    print(f"\n[*] Database: {DB_PATH}")
    engine = get_engine()
    db = sessionmaker(bind=engine)()

    try:
        print("\n[1/7] Creating super_admin user...")
        admin_id, is_super = ensure_super_admin(db)
        if not is_super:
            print(f"  [WARN] User '{ADMIN_USERNAME}' exists but role is not super_admin")

        print("\n[2/7] Setting user_id on existing data...")
        migrate(db, admin_id)

        print("\n[3/7] Rebuilding unique constraints...")
        rebuild_unique_constraints(db, engine, admin_id)

        print("\n[4/7] Migrating applicant_profile...")
        ensure_applicant_profile(db, admin_id)

        print("\n[5/7] Migrating portfolio tables...")
        ensure_portfolio_tables(db, admin_id)

        print("\n[6/7] Creating default UserConfig...")
        ensure_user_config(db, admin_id)

        print("\n[7/7] Copying global knowledge to admin user dir...")
        copy_knowledge_to_user_dir(admin_id)

        print("\n" + "=" * 60)
        print("  Migration completed successfully!")
        print(f"  Admin user id: {admin_id}")
        print("=" * 60)
        print()
        print("All existing data is now owned by the super_admin user.")
        print("Users should re-login to obtain new JWT tokens with user_id.")

    except Exception as e:
        db.rollback()
        print(f"\n[FATAL] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
