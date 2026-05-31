"""
Local SQLite schema migration — run once to bring instance/mvp.db up to date.
Safe to re-run (uses ADD COLUMN IF NOT EXISTS workaround for SQLite).
"""
import sqlite3, os, sys

db_path = os.path.join(os.path.dirname(__file__), "instance", "mvp.db")
if not os.path.exists(db_path):
    print(f"ERROR: DB not found at {db_path}")
    sys.exit(1)

conn = sqlite3.connect(db_path)
c    = conn.cursor()

# ── 1. Add tenant_id to tables that need tenant scoping ─────────────────────
for table_name in ["users", "leads", "projects", "activity_logs"]:
    cols = [r[1] for r in c.execute(f"PRAGMA table_info({table_name})").fetchall()]
    if "tenant_id" not in cols:
        c.execute(
            f"ALTER TABLE {table_name} ADD COLUMN tenant_id INTEGER REFERENCES tenants(id)"
        )
        print(f"  + {table_name}.tenant_id added")
    else:
        print(f"  . {table_name}.tenant_id already exists")

# ── 2. Create otp_codes table if missing ─────────────────────────────────────
tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
if "otp_codes" not in tables:
    c.execute("""
        CREATE TABLE otp_codes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            email       TEXT    NOT NULL,
            otp_hash    TEXT    NOT NULL,
            tenant_slug TEXT,
            expires_at  DATETIME NOT NULL,
            used        INTEGER  NOT NULL DEFAULT 0,
            attempts    INTEGER  NOT NULL DEFAULT 0,
            ip_address  TEXT,
            created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("CREATE INDEX ix_otp_codes_email      ON otp_codes (email)")
    c.execute("CREATE INDEX ix_otp_codes_expires_at ON otp_codes (expires_at)")
    print("  + otp_codes table created")
else:
    print("  . otp_codes already exists")

conn.commit()
conn.close()
print("Local SQLite migration complete.")
