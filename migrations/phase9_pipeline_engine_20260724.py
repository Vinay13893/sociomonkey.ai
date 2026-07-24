"""Additive Phase 9 unified Lead Pipeline Engine migration."""

import argparse
import os
import sys
from urllib.parse import urlparse

import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db_safety import get_database_url


CAPABILITIES = [
    ('pipeline.view', 'VIEW', 'View permitted Lead pipeline records'),
    ('pipeline.move', 'EDIT', 'Move permitted Leads through pipeline stages'),
    ('pipeline.assign', 'ASSIGN', 'Assign permitted Lead pipeline ownership'),
    ('pipeline.override', 'APPROVE', 'Override configured pipeline requirements'),
    ('pipeline.configure', 'CONFIGURE', 'Configure tenant Pipeline stages'),
]

DDL = """
ALTER TABLE IF EXISTS lead_status_configurations
 ADD COLUMN IF NOT EXISTS is_success BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE IF EXISTS lead_status_configurations
 ADD COLUMN IF NOT EXISTS entry_rule_keys JSON NOT NULL DEFAULT '[]';
ALTER TABLE IF EXISTS lead_status_configurations
 ADD COLUMN IF NOT EXISTS exit_rule_keys JSON NOT NULL DEFAULT '[]';
ALTER TABLE IF EXISTS lead_status_configurations
 ADD COLUMN IF NOT EXISTS required_action_type_keys JSON NOT NULL DEFAULT '[]';
ALTER TABLE IF EXISTS lead_status_configurations
 ADD COLUMN IF NOT EXISTS default_actions JSON NOT NULL DEFAULT '[]';
ALTER TABLE IF EXISTS leads
 ADD COLUMN IF NOT EXISTS channel_partner_id
 INTEGER REFERENCES channel_partners(id);
CREATE INDEX IF NOT EXISTS ix_leads_channel_partner
 ON leads(channel_partner_id) WHERE channel_partner_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS pipeline_transitions (
 id SERIAL PRIMARY KEY,
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 lead_id INTEGER NOT NULL REFERENCES leads(id),
 from_stage_key VARCHAR(80),
 to_stage_key VARCHAR(80) NOT NULL,
 changed_by_user_id INTEGER REFERENCES users(id),
 source VARCHAR(80) NOT NULL DEFAULT 'PIPELINE',
 reason TEXT,
 correlation_id VARCHAR(36) NOT NULL,
 rule_evaluation JSON NOT NULL DEFAULT '{}',
 transition_context JSON NOT NULL DEFAULT '{}',
 previous_owner_id INTEGER REFERENCES users(id),
 current_owner_id INTEGER REFERENCES users(id),
 manager_override BOOLEAN NOT NULL DEFAULT FALSE,
 visit_id INTEGER REFERENCES visits(id),
 channel_partner_id INTEGER REFERENCES channel_partners(id),
 created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_pipeline_transitions_tenant_stage_created
 ON pipeline_transitions(tenant_id,to_stage_key,created_at);
CREATE INDEX IF NOT EXISTS ix_pipeline_transitions_tenant_lead_created
 ON pipeline_transitions(tenant_id,lead_id,created_at);
CREATE INDEX IF NOT EXISTS ix_pipeline_transitions_correlation
 ON pipeline_transitions(correlation_id);
CREATE INDEX IF NOT EXISTS ix_pipeline_transitions_visit
 ON pipeline_transitions(visit_id) WHERE visit_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_pipeline_transitions_channel_partner
 ON pipeline_transitions(channel_partner_id)
 WHERE channel_partner_id IS NOT NULL;
CREATE OR REPLACE FUNCTION reject_pipeline_transition_mutation()
RETURNS trigger AS $$
BEGIN
 RAISE EXCEPTION 'pipeline_transitions are immutable';
END;
$$ LANGUAGE plpgsql;
DO $$
BEGIN
 IF NOT EXISTS (
   SELECT 1 FROM pg_trigger
   WHERE tgname='pipeline_transitions_immutable'
     AND tgrelid='pipeline_transitions'::regclass
 ) THEN
   CREATE TRIGGER pipeline_transitions_immutable
   BEFORE UPDATE OR DELETE ON pipeline_transitions
   FOR EACH ROW EXECUTE FUNCTION reject_pipeline_transition_mutation();
 END IF;
END;
$$;

ALTER TABLE IF EXISTS lead_assignment_history
 ADD COLUMN IF NOT EXISTS tenant_id INTEGER REFERENCES tenants(id);
ALTER TABLE IF EXISTS lead_assignment_history
 ADD COLUMN IF NOT EXISTS source VARCHAR(80) NOT NULL DEFAULT 'LEADS';
ALTER TABLE IF EXISTS lead_assignment_history
 ADD COLUMN IF NOT EXISTS correlation_id VARCHAR(36);
ALTER TABLE IF EXISTS lead_assignment_history
 ADD COLUMN IF NOT EXISTS is_manager_override BOOLEAN NOT NULL DEFAULT FALSE;
CREATE INDEX IF NOT EXISTS ix_lead_assignment_history_tenant_lead
 ON lead_assignment_history(tenant_id,lead_id);
CREATE INDEX IF NOT EXISTS ix_lead_assignment_history_correlation
 ON lead_assignment_history(correlation_id);

ALTER TABLE IF EXISTS notification_events
 ADD COLUMN IF NOT EXISTS pipeline_transition_id
 INTEGER REFERENCES pipeline_transitions(id);
CREATE INDEX IF NOT EXISTS ix_notification_events_pipeline_transition
 ON notification_events(pipeline_transition_id)
 WHERE pipeline_transition_id IS NOT NULL;
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
             AND table_name='pipeline_transitions'"""
    )
    table = cursor.fetchone()[0]
    cursor.execute(
        """SELECT column_name FROM information_schema.columns
           WHERE table_schema=current_schema()
             AND table_name='lead_status_configurations'
             AND column_name=ANY(%s)""",
        ([
            'is_success', 'entry_rule_keys', 'exit_rule_keys',
            'required_action_type_keys', 'default_actions',
        ],),
    )
    status_columns = sorted(row[0] for row in cursor.fetchall())
    cursor.execute(
        """SELECT column_name FROM information_schema.columns
           WHERE table_schema=current_schema()
             AND table_name='lead_assignment_history'
             AND column_name=ANY(%s)""",
        ([
            'tenant_id', 'source', 'correlation_id',
            'is_manager_override',
        ],),
    )
    assignment_columns = sorted(row[0] for row in cursor.fetchall())
    cursor.execute(
        """SELECT COUNT(*) FROM information_schema.columns
           WHERE table_schema=current_schema()
             AND table_name='notification_events'
             AND column_name='pipeline_transition_id'"""
    )
    notification_link = cursor.fetchone()[0]
    cursor.execute(
        """SELECT COUNT(*) FROM information_schema.columns
           WHERE table_schema=current_schema()
             AND table_name='leads'
             AND column_name='channel_partner_id'"""
    )
    lead_partner_link = cursor.fetchone()[0]
    cursor.execute(
        """SELECT COUNT(*) FROM permission_definitions
           WHERE key LIKE 'pipeline.%'"""
    )
    capabilities = cursor.fetchone()[0]
    cursor.execute(
        """SELECT COUNT(*) FROM pg_trigger
           WHERE tgname='pipeline_transitions_immutable'
             AND tgrelid=to_regclass('pipeline_transitions')
             AND NOT tgisinternal"""
    )
    immutable_trigger = cursor.fetchone()[0]
    return {
        'pipeline_table': table,
        'immutable_trigger': immutable_trigger,
        'status_columns': status_columns,
        'assignment_columns': assignment_columns,
        'notification_link': notification_link,
        'lead_partner_link': lead_partner_link,
        'capabilities': capabilities,
    }


def _seed_permissions(cursor):
    for key, action, description in CAPABILITIES:
        cursor.execute(
            """INSERT INTO permission_definitions(
                 key,module,action,description
               ) VALUES(%s,'pipeline',%s,%s)
               ON CONFLICT(key) DO NOTHING""",
            (key, action, description),
        )
    all_keys = [row[0] for row in CAPABILITIES]
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
                 AND rp.scope_ref_id IS NULL AND rp.effect='ALLOW'
             )
           ON CONFLICT DO NOTHING""",
        (all_keys,),
    )
    manager_keys = [
        'pipeline.view', 'pipeline.move', 'pipeline.assign',
        'pipeline.override',
    ]
    cursor.execute(
        """INSERT INTO role_permissions(
             tenant_id,business_role_id,permission_id,scope_type,effect
           )
           SELECT br.tenant_id,br.id,p.id,'TEAM','ALLOW'
           FROM business_roles br
           JOIN permission_definitions p ON p.key=ANY(%s)
           WHERE br.key IN('CALLING_MANAGER','SALES_MANAGER')
             AND br.tenant_id IS NOT NULL
             AND NOT EXISTS(
               SELECT 1 FROM role_permissions rp
               WHERE rp.business_role_id=br.id
                 AND rp.permission_id=p.id
                 AND rp.scope_type='TEAM'
                 AND rp.scope_ref_id IS NULL AND rp.effect='ALLOW'
             )
           ON CONFLICT DO NOTHING""",
        (manager_keys,),
    )
    cursor.execute(
        """INSERT INTO role_permissions(
             tenant_id,business_role_id,permission_id,scope_type,effect
           )
           SELECT br.tenant_id,br.id,p.id,'OWN','ALLOW'
           FROM business_roles br
           JOIN permission_definitions p
             ON p.key=ANY(%s)
           WHERE br.key IN(
             'CALLER','RELATIONSHIP_MANAGER','RECEPTION',
             'LEGACY_TEAM_MEMBER'
           ) AND br.tenant_id IS NOT NULL
             AND NOT EXISTS(
               SELECT 1 FROM role_permissions rp
               WHERE rp.business_role_id=br.id
                 AND rp.permission_id=p.id
                 AND rp.scope_type='OWN'
                 AND rp.scope_ref_id IS NULL AND rp.effect='ALLOW'
             )
           ON CONFLICT DO NOTHING""",
        (['pipeline.view', 'pipeline.move'],),
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
                expected_status = 5
                expected_assignments = 4
                if (
                    after['pipeline_table'] != 1
                    or after['immutable_trigger'] != 1
                    or len(after['status_columns']) != expected_status
                    or len(after['assignment_columns']) != expected_assignments
                    or after['notification_link'] != 1
                    or after['lead_partner_link'] != 1
                    or after['capabilities'] != len(CAPABILITIES)
                ):
                    raise RuntimeError(after)
                print(f'After: {after}')
        connection.commit()


if __name__ == '__main__':
    main()
