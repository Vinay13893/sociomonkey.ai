"""Additive Phase 13a lead co-ownership migration.

Adds the two pre-sales co-owner slots (calling_manager_id, caller_id) to
leads, concurrent with the existing sales-side slots (sales_manager_id,
assigned_to) rather than replacing them - see app/models/lead.py for the
rationale. Also adds role_slot to lead_assignment_history so history entries
can record which slot changed. Both changes are nullable/additive; no
existing column, row, or behaviour is altered.
"""
import argparse
import os
import sys
from urllib.parse import urlparse

import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db_safety import get_database_url


DDL = """
ALTER TABLE IF EXISTS leads
 ADD COLUMN IF NOT EXISTS calling_manager_id INTEGER REFERENCES users(id);
ALTER TABLE IF EXISTS leads
 ADD COLUMN IF NOT EXISTS caller_id INTEGER REFERENCES users(id);
ALTER TABLE IF EXISTS lead_assignment_history
 ADD COLUMN IF NOT EXISTS role_slot VARCHAR(20);
"""


def _guard(url):
    actual = (urlparse(url).hostname or '').lower()
    expected = (os.getenv('EXPECTED_DATABASE_HOST') or '').strip().lower()
    if not expected or actual != expected:
        raise SystemExit(
            'ERROR: DATABASE_URL host does not match EXPECTED_DATABASE_HOST.'
        )


def _state(cursor):
    cursor.execute(
        """SELECT column_name FROM information_schema.columns
           WHERE table_schema=current_schema()
             AND table_name='leads'
             AND column_name=ANY(%s)""",
        (['calling_manager_id', 'caller_id'],),
    )
    lead_columns = sorted(row[0] for row in cursor.fetchall())
    cursor.execute(
        """SELECT column_name FROM information_schema.columns
           WHERE table_schema=current_schema()
             AND table_name='lead_assignment_history'
             AND column_name='role_slot'"""
    )
    history_columns = sorted(row[0] for row in cursor.fetchall())
    return {'lead_columns': lead_columns, 'history_columns': history_columns}


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    url = get_database_url(require_production_confirmation=False)
    _guard(url)
    with psycopg2.connect(url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout='30s'")
            print(f'Before: {_state(cursor)}')
            if args.apply:
                cursor.execute(DDL)
                after = _state(cursor)
                if len(after['lead_columns']) != 2 or len(after['history_columns']) != 1:
                    raise RuntimeError(after)
                print(f'After: {after}')
        connection.commit()


if __name__ == '__main__':
    main()
