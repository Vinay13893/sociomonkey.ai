"""Additive: add visits.sales_manager_id (nullable FK to users).

Co-owner alongside assigned_user_id, mirroring the Lead co-ownership
model - for a Channel Partner meeting, assigned_user_id is the RM
actually attending and sales_manager_id is their manager, so hierarchy
reporting doesn't have to infer it from the org chart at query time.
Idempotent - safe to re-run.
"""
import argparse
import os
import sys
from urllib.parse import urlparse

import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db_safety import get_database_url

DDL = r"""
ALTER TABLE visits ADD COLUMN IF NOT EXISTS sales_manager_id INTEGER REFERENCES users(id);
CREATE INDEX IF NOT EXISTS ix_visits_sales_manager_id ON visits(sales_manager_id);
"""


def _host_guard(url):
    actual = (urlparse(url).hostname or '').lower()
    expected = (os.environ.get('EXPECTED_DATABASE_HOST') or '').strip().lower()
    if not expected or actual != expected:
        raise SystemExit('ERROR: DATABASE_URL host does not match required EXPECTED_DATABASE_HOST.')


def _state(cur):
    cur.execute("""SELECT column_name FROM information_schema.columns
                   WHERE table_name='visits' AND column_name='sales_manager_id'""")
    return bool(cur.fetchall())


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    url = get_database_url()
    _host_guard(url)
    with psycopg2.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout='30s'")
            print(f'Before: column present = {_state(cur)}')
            if args.apply:
                cur.execute(DDL)
                present = _state(cur)
                if not present:
                    raise RuntimeError('Migration validation failed: column still missing')
                print(f'After: column present = {present}')
        conn.commit()


if __name__ == '__main__':
    main()
