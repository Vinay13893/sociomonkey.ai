"""Additive/relaxing: visits.location_id becomes nullable.

Not every Visit happens at a registered Location - a Channel Partner
meeting is commonly at the partner's own office, and Location was the
only way to describe where a meeting happens (paired with an optional
free-text venue_note in operational_metadata for anything else). The
generic POST /api/visits path (app.services.visit_builder.
validate_visit_payload) no longer requires it; Reception's separate
walk-in intake (app.routes.gallery_operations) has its own independent
code path and is unaffected. Idempotent - safe to re-run.
"""
import argparse
import os
import sys
from urllib.parse import urlparse

import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db_safety import get_database_url

DDL = "ALTER TABLE visits ALTER COLUMN location_id DROP NOT NULL;"


def _host_guard(url):
    actual = (urlparse(url).hostname or '').lower()
    expected = (os.environ.get('EXPECTED_DATABASE_HOST') or '').strip().lower()
    if not expected or actual != expected:
        raise SystemExit('ERROR: DATABASE_URL host does not match required EXPECTED_DATABASE_HOST.')


def _state(cur):
    cur.execute("""SELECT is_nullable FROM information_schema.columns
                   WHERE table_name='visits' AND column_name='location_id'""")
    row = cur.fetchone()
    return row[0] if row else None


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
            print(f'Before: is_nullable = {_state(cur)}')
            if args.apply:
                cur.execute(DDL)
                nullable = _state(cur)
                if nullable != 'YES':
                    raise RuntimeError(f'Migration validation failed: is_nullable={nullable}')
                print(f'After: is_nullable = {nullable}')
        conn.commit()


if __name__ == '__main__':
    main()
