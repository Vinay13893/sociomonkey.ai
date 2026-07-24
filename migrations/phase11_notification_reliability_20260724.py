"""Additive Phase 11 notification reliability migration."""

import argparse
import os
import sys
from urllib.parse import urlparse

import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db_safety import get_database_url


CAPABILITIES = [
    (
        'notifications.manage',
        'MANAGE',
        'Manage tenant notification operations and completed-event archives',
    ),
    (
        'notifications.retry',
        'MANAGE',
        'Replay failed tenant notification delivery events',
    ),
]

DDL = """
ALTER TABLE IF EXISTS push_subscriptions
 ADD COLUMN IF NOT EXISTS failure_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE IF EXISTS push_subscriptions
 ADD COLUMN IF NOT EXISTS last_success_at TIMESTAMP;
ALTER TABLE IF EXISTS push_subscriptions
 ADD COLUMN IF NOT EXISTS last_failure_at TIMESTAMP;
ALTER TABLE IF EXISTS push_subscriptions
 ADD COLUMN IF NOT EXISTS deactivated_at TIMESTAMP;
ALTER TABLE IF EXISTS push_subscriptions
 ADD COLUMN IF NOT EXISTS deactivation_reason VARCHAR(80);

ALTER TABLE IF EXISTS notification_events
 ADD COLUMN IF NOT EXISTS failure_category VARCHAR(50);
ALTER TABLE IF EXISTS notification_events
 ADD COLUMN IF NOT EXISTS last_attempt_at TIMESTAMP;
ALTER TABLE IF EXISTS notification_events
 ADD COLUMN IF NOT EXISTS replay_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE IF EXISTS notification_events
 ADD COLUMN IF NOT EXISTS replayed_at TIMESTAMP;
ALTER TABLE IF EXISTS notification_events
 ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP;
ALTER TABLE IF EXISTS notification_events
 ADD COLUMN IF NOT EXISTS origin_type VARCHAR(80);
ALTER TABLE IF EXISTS notification_events
 ADD COLUMN IF NOT EXISTS origin_id INTEGER;
ALTER TABLE IF EXISTS notification_events
 ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW();

ALTER TABLE IF EXISTS notifications
 ADD COLUMN IF NOT EXISTS correlation_id VARCHAR(36);
ALTER TABLE IF EXISTS callback_reminders
 ADD COLUMN IF NOT EXISTS correlation_id VARCHAR(36);

CREATE INDEX IF NOT EXISTS ix_notification_events_failure_category
 ON notification_events(failure_category);
CREATE INDEX IF NOT EXISTS ix_notification_events_archived_at
 ON notification_events(archived_at);
CREATE INDEX IF NOT EXISTS ix_notification_events_origin_type
 ON notification_events(origin_type);
CREATE INDEX IF NOT EXISTS ix_notification_events_tenant_queue_due
 ON notification_events(tenant_id,status,scheduled_for,id)
 WHERE archived_at IS NULL;
CREATE INDEX IF NOT EXISTS ix_notification_events_tenant_dead_letter
 ON notification_events(tenant_id,dead_lettered_at)
 WHERE dead_lettered_at IS NOT NULL AND archived_at IS NULL;
CREATE INDEX IF NOT EXISTS ix_notifications_correlation_id
 ON notifications(correlation_id);
CREATE INDEX IF NOT EXISTS ix_callback_reminders_correlation_id
 ON callback_reminders(correlation_id);

CREATE TABLE IF NOT EXISTS notification_delivery_attempts (
 id SERIAL PRIMARY KEY,
 tenant_id INTEGER REFERENCES tenants(id),
 notification_event_id INTEGER NOT NULL REFERENCES notification_events(id),
 push_subscription_id INTEGER REFERENCES push_subscriptions(id),
 correlation_id VARCHAR(36),
 worker_run_id VARCHAR(36) NOT NULL,
 attempt_number INTEGER NOT NULL,
 outcome VARCHAR(30) NOT NULL,
 failure_category VARCHAR(50),
 provider_status INTEGER,
 error_summary VARCHAR(400),
 duration_ms INTEGER,
 next_retry_at TIMESTAMP,
 created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_notification_attempts_tenant_created
 ON notification_delivery_attempts(tenant_id,created_at);
CREATE INDEX IF NOT EXISTS ix_notification_attempts_event_created
 ON notification_delivery_attempts(notification_event_id,created_at);
CREATE INDEX IF NOT EXISTS ix_notification_attempts_subscription
 ON notification_delivery_attempts(push_subscription_id)
 WHERE push_subscription_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_notification_attempts_correlation
 ON notification_delivery_attempts(correlation_id);
CREATE INDEX IF NOT EXISTS ix_notification_attempts_worker_run
 ON notification_delivery_attempts(worker_run_id);
CREATE INDEX IF NOT EXISTS ix_notification_attempts_outcome_failure
 ON notification_delivery_attempts(outcome,failure_category,created_at);

CREATE OR REPLACE FUNCTION reject_notification_attempt_mutation()
RETURNS trigger AS $$
BEGIN
 RAISE EXCEPTION 'notification_delivery_attempts are immutable';
END;
$$ LANGUAGE plpgsql;
DO $$
BEGIN
 IF NOT EXISTS (
   SELECT 1 FROM pg_trigger
   WHERE tgname='notification_delivery_attempts_immutable'
     AND tgrelid='notification_delivery_attempts'::regclass
 ) THEN
   CREATE TRIGGER notification_delivery_attempts_immutable
   BEFORE UPDATE OR DELETE ON notification_delivery_attempts
   FOR EACH ROW EXECUTE FUNCTION reject_notification_attempt_mutation();
 END IF;
END;
$$;
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
        """SELECT COUNT(*) FROM information_schema.tables
           WHERE table_schema=current_schema()
             AND table_name='notification_delivery_attempts'"""
    )
    attempt_table = cursor.fetchone()[0]
    cursor.execute(
        """SELECT column_name FROM information_schema.columns
           WHERE table_schema=current_schema()
             AND table_name='notification_events'
             AND column_name=ANY(%s)""",
        ([
            'failure_category', 'last_attempt_at', 'replay_count',
            'replayed_at', 'archived_at', 'origin_type', 'origin_id',
            'updated_at',
        ],),
    )
    event_columns = sorted(row[0] for row in cursor.fetchall())
    cursor.execute(
        """SELECT column_name FROM information_schema.columns
           WHERE table_schema=current_schema()
             AND table_name='push_subscriptions'
             AND column_name=ANY(%s)""",
        ([
            'failure_count', 'last_success_at', 'last_failure_at',
            'deactivated_at', 'deactivation_reason',
        ],),
    )
    subscription_columns = sorted(row[0] for row in cursor.fetchall())
    cursor.execute(
        """SELECT COUNT(*) FROM information_schema.columns
           WHERE table_schema=current_schema()
             AND ((table_name='notifications' AND column_name='correlation_id')
               OR (table_name='callback_reminders'
                   AND column_name='correlation_id'))"""
    )
    correlation_columns = cursor.fetchone()[0]
    cursor.execute(
        """SELECT COUNT(*) FROM pg_trigger
           WHERE tgname='notification_delivery_attempts_immutable'
             AND tgrelid=to_regclass('notification_delivery_attempts')
             AND NOT tgisinternal"""
    )
    immutable_trigger = cursor.fetchone()[0]
    cursor.execute(
        """SELECT COUNT(*) FROM permission_definitions
           WHERE key=ANY(%s)""",
        ([row[0] for row in CAPABILITIES],),
    )
    capabilities = cursor.fetchone()[0]
    return {
        'attempt_table': attempt_table,
        'attempt_immutable': immutable_trigger,
        'event_columns': event_columns,
        'subscription_columns': subscription_columns,
        'correlation_columns': correlation_columns,
        'capabilities': capabilities,
    }


def _seed_permissions(cursor):
    for key, action, description in CAPABILITIES:
        cursor.execute(
            """INSERT INTO permission_definitions(
                 key,module,action,description
               ) VALUES(%s,'notifications',%s,%s)
               ON CONFLICT(key) DO NOTHING""",
            (key, action, description),
        )
    keys = [row[0] for row in CAPABILITIES]
    cursor.execute(
        """INSERT INTO role_permissions(
             tenant_id,business_role_id,permission_id,scope_type,effect
           )
           SELECT br.tenant_id,br.id,p.id,
             CASE WHEN br.key='PLATFORM_OWNER' THEN 'PLATFORM' ELSE 'TENANT' END,
             'ALLOW'
           FROM business_roles br
           JOIN permission_definitions p ON p.key=ANY(%s)
           WHERE br.key IN('PLATFORM_OWNER','ADMIN')
             AND NOT EXISTS(
               SELECT 1 FROM role_permissions rp
               WHERE rp.business_role_id=br.id
                 AND rp.permission_id=p.id
                 AND rp.scope_type=CASE
                   WHEN br.key='PLATFORM_OWNER' THEN 'PLATFORM' ELSE 'TENANT'
                 END
                 AND rp.scope_ref_id IS NULL
                 AND rp.effect='ALLOW'
             )
           ON CONFLICT DO NOTHING""",
        (keys,),
    )


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
                _seed_permissions(cursor)
                after = _state(cursor)
                if (
                    after['attempt_table'] != 1
                    or after['attempt_immutable'] != 1
                    or len(after['event_columns']) != 8
                    or len(after['subscription_columns']) != 5
                    or after['correlation_columns'] != 2
                    or after['capabilities'] != len(CAPABILITIES)
                ):
                    raise RuntimeError(after)
                print(f'After: {after}')
        connection.commit()


if __name__ == '__main__':
    main()
