"""Additive Phase 1 reliability fields for ingestion and notification queues.

Validation first:
  set DATABASE_URL to the Neon recovery branch
  set EXPECTED_DATABASE_HOST to that branch's exact host
  set ALLOW_PRODUCTION_DB_OPERATION=true
  python migrations/phase1_reliability_20260722.py --check
  python migrations/phase1_reliability_20260722.py --apply
  python migrations/phase1_reliability_20260722.py --check

The migration never drops, renames, truncates, or rewrites existing records.
"""
import argparse
import os
import sys
from urllib.parse import urlparse

import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db_safety import get_database_url


EXPECTED_COLUMNS = {
    'ingested_lead_logs': {
        'correlation_id', 'idempotency_key', 'attempt_count',
        'last_attempt_at', 'next_retry_at',
    },
    'notification_events': {
        'correlation_id', 'idempotency_key', 'claimed_at', 'dead_lettered_at',
    },
}

STATEMENTS = (
    'ALTER TABLE ingested_lead_logs ADD COLUMN IF NOT EXISTS correlation_id VARCHAR(36)',
    'ALTER TABLE ingested_lead_logs ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(300)',
    'ALTER TABLE ingested_lead_logs ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 0',
    'ALTER TABLE ingested_lead_logs ADD COLUMN IF NOT EXISTS last_attempt_at TIMESTAMP',
    'ALTER TABLE ingested_lead_logs ADD COLUMN IF NOT EXISTS next_retry_at TIMESTAMP',
    'CREATE INDEX IF NOT EXISTS ix_ingested_lead_logs_correlation_id ON ingested_lead_logs (correlation_id)',
    'CREATE UNIQUE INDEX IF NOT EXISTS uq_ingested_log_idempotency_key ON ingested_lead_logs (idempotency_key) WHERE idempotency_key IS NOT NULL',
    'ALTER TABLE notification_events ADD COLUMN IF NOT EXISTS correlation_id VARCHAR(36)',
    'ALTER TABLE notification_events ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(300)',
    'ALTER TABLE notification_events ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMP',
    'ALTER TABLE notification_events ADD COLUMN IF NOT EXISTS dead_lettered_at TIMESTAMP',
    'CREATE INDEX IF NOT EXISTS ix_notification_events_correlation_id ON notification_events (correlation_id)',
    'CREATE INDEX IF NOT EXISTS ix_notification_events_claimed_at ON notification_events (claimed_at)',
    'CREATE UNIQUE INDEX IF NOT EXISTS uq_notification_event_idempotency_key ON notification_events (idempotency_key) WHERE idempotency_key IS NOT NULL',
)


def _assert_expected_host(database_url):
    actual = (urlparse(database_url).hostname or '').strip().lower()
    expected = (os.environ.get('EXPECTED_DATABASE_HOST') or '').strip().lower()
    if not expected:
        raise SystemExit('ERROR: EXPECTED_DATABASE_HOST is required.')
    if actual != expected:
        raise SystemExit('ERROR: DATABASE_URL host does not match EXPECTED_DATABASE_HOST.')


def _schema_state(cursor):
    state = {}
    for table, expected in EXPECTED_COLUMNS.items():
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = %s
            """,
            (table,),
        )
        present = {row[0] for row in cursor.fetchall()}
        state[table] = {
            'present': sorted(expected & present),
            'missing': sorted(expected - present),
        }
    return state


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--apply', action='store_true')
    args = parser.parse_args()

    database_url = get_database_url()
    _assert_expected_host(database_url)

    with psycopg2.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '30s'")
            before = _schema_state(cursor)
            print(f'Before: {before}')
            if args.apply:
                for statement in STATEMENTS:
                    cursor.execute(statement)
                after = _schema_state(cursor)
                missing = {table: data['missing'] for table, data in after.items() if data['missing']}
                if missing:
                    raise RuntimeError(f'Migration validation failed: {missing}')
                print(f'After: {after}')
            connection.commit()


if __name__ == '__main__':
    main()
