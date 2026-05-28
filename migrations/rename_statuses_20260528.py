"""
Migration: rename_statuses_20260528
====================================
Renames lead statuses to the new naming convention:

  attempted  → no_answer
  connected  → follow_up

Affected tables:
  - leads.status
  - status_history.old_status
  - status_history.new_status

NOTE: activity_logs.old_value / new_value store free-text descriptions
and are intentionally NOT migrated — they are historical audit records.
Old exports / reports that reference "attempted" or "connected" remain
readable through the STATUS_ALIASES map in app/utils/leads.py.

Run:
  cd backend
  python migrations/rename_statuses_20260528.py

Set DATABASE_URL env var to point at Neon (production) or leave unset to
run against the local SQLite instance.
"""
import os
import sys

# Allow running from the backend root
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app
from app import db
from sqlalchemy import text

RENAMES = [
    ('attempted', 'no_answer'),
    ('connected',  'follow_up'),
]


def run_migration():
    app = create_app(os.getenv('FLASK_ENV', 'production'))

    with app.app_context():
        conn = db.engine.connect()
        trans = conn.begin()
        try:
            for old, new in RENAMES:
                # leads table
                res = conn.execute(
                    text("UPDATE leads SET status = :new WHERE status = :old"),
                    {"new": new, "old": old},
                )
                print(f"leads.status: {old!r} → {new!r}  ({res.rowcount} rows)")

                # status_history — old_status column
                res = conn.execute(
                    text("UPDATE status_history SET old_status = :new WHERE old_status = :old"),
                    {"new": new, "old": old},
                )
                print(f"status_history.old_status: {old!r} → {new!r}  ({res.rowcount} rows)")

                # status_history — new_status column
                res = conn.execute(
                    text("UPDATE status_history SET new_status = :new WHERE new_status = :old"),
                    {"new": new, "old": old},
                )
                print(f"status_history.new_status: {old!r} → {new!r}  ({res.rowcount} rows)")

            trans.commit()
            print("\n✅  Migration committed successfully.")

        except Exception as exc:
            trans.rollback()
            print(f"\n❌  Migration FAILED — rolled back.  Error: {exc}")
            sys.exit(1)
        finally:
            conn.close()


if __name__ == '__main__':
    run_migration()
