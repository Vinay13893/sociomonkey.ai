"""Additive Phase 5 unified Visit foundation."""

import argparse
import os
import sys
from urllib.parse import urlparse

import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db_safety import get_database_url


TABLES = {
    'visit_type_configurations', 'visit_status_configurations', 'visits',
    'visit_participants', 'visit_tags', 'visit_attachments',
}

VISIT_TYPES = [
    ('SCHEDULED_VISIT', 'Scheduled Visit', 10, '#2563eb'),
    ('WALK_IN', 'Walk-in', 20, '#0f766e'),
    ('DIRECT_PROJECT_SITE', 'Direct Project Site Visit', 30, '#0891b2'),
    ('EXISTING_LEAD', 'Existing Lead Visit', 40, '#7c3aed'),
    ('CHANNEL_PARTNER', 'Channel Partner Visit', 50, '#d97706'),
    ('CHANNEL_PARTNER_CUSTOMERS', 'Channel Partner with Customer(s)', 60, '#ea580c'),
    ('INTERNAL_MEETING', 'Internal Meeting', 70, '#475569'),
    ('WORKSPACE_USAGE', 'Workspace Usage', 80, '#059669'),
    ('DOCUMENTATION', 'Documentation Visit', 90, '#4f46e5'),
    ('EVENT_CAMPAIGN', 'Event / Campaign Visit', 100, '#db2777'),
    ('OTHER', 'Other', 110, '#64748b'),
]

VISIT_STATUSES = [
    ('SCHEDULED', 'Scheduled', 10, '#2563eb', False),
    ('CHECKED_IN', 'Checked In', 20, '#0f766e', False),
    ('IN_PROGRESS', 'In Progress', 30, '#d97706', False),
    ('COMPLETED', 'Completed', 40, '#16a34a', True),
    ('CANCELLED', 'Cancelled', 50, '#dc2626', True),
    ('NO_SHOW', 'No Show', 60, '#7c3aed', True),
]

DDL = """
CREATE TABLE IF NOT EXISTS visit_type_configurations (
 id SERIAL PRIMARY KEY, tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 internal_key VARCHAR(80) NOT NULL, display_name VARCHAR(160) NOT NULL,
 display_order INTEGER NOT NULL DEFAULT 0, colour VARCHAR(20) NOT NULL DEFAULT '#64748b',
 is_active BOOLEAN NOT NULL DEFAULT TRUE, visibility VARCHAR(20) NOT NULL DEFAULT 'VISIBLE',
 updated_by INTEGER REFERENCES users(id), created_at TIMESTAMP NOT NULL DEFAULT NOW(),
 updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
 CONSTRAINT uq_visit_type_tenant_key UNIQUE(tenant_id,internal_key),
 CONSTRAINT ck_visit_type_visibility CHECK(visibility IN('VISIBLE','HIDDEN'))
);
CREATE TABLE IF NOT EXISTS visit_status_configurations (
 id SERIAL PRIMARY KEY, tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 internal_key VARCHAR(80) NOT NULL, display_name VARCHAR(160) NOT NULL,
 display_order INTEGER NOT NULL DEFAULT 0, colour VARCHAR(20) NOT NULL DEFAULT '#64748b',
 is_active BOOLEAN NOT NULL DEFAULT TRUE, is_terminal BOOLEAN NOT NULL DEFAULT FALSE,
 visibility VARCHAR(20) NOT NULL DEFAULT 'VISIBLE',
 updated_by INTEGER REFERENCES users(id), created_at TIMESTAMP NOT NULL DEFAULT NOW(),
 updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
 CONSTRAINT uq_visit_status_tenant_key UNIQUE(tenant_id,internal_key),
 CONSTRAINT ck_visit_status_visibility CHECK(visibility IN('VISIBLE','HIDDEN'))
);
CREATE TABLE IF NOT EXISTS visits (
 id SERIAL PRIMARY KEY, tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 visit_type_key VARCHAR(80) NOT NULL, status_key VARCHAR(80) NOT NULL DEFAULT 'SCHEDULED',
 location_id INTEGER NOT NULL REFERENCES locations(id),
 meeting_room_id INTEGER REFERENCES meeting_rooms(id), project_id INTEGER REFERENCES projects(id),
 lead_id INTEGER REFERENCES leads(id), assigned_user_id INTEGER REFERENCES users(id),
 purpose VARCHAR(250), notes TEXT, expected_arrival TIMESTAMP,
 actual_check_in TIMESTAMP, actual_check_out TIMESTAMP,
 visitor_count INTEGER NOT NULL DEFAULT 1, source VARCHAR(120),
 priority VARCHAR(30) NOT NULL DEFAULT 'NORMAL',
 operational_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
 reception_assigned_user_id INTEGER REFERENCES users(id),
 escort_user_id INTEGER REFERENCES users(id), token_code VARCHAR(80),
 is_active BOOLEAN NOT NULL DEFAULT TRUE, archived_at TIMESTAMP,
 created_by INTEGER NOT NULL REFERENCES users(id), updated_by INTEGER NOT NULL REFERENCES users(id),
 created_at TIMESTAMP NOT NULL DEFAULT NOW(), updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
 CONSTRAINT ck_visit_visitor_count_positive CHECK(visitor_count>0),
 CONSTRAINT ck_visit_priority CHECK(priority IN('LOW','NORMAL','HIGH','URGENT')),
 CONSTRAINT ck_visit_chronology CHECK(
   actual_check_in IS NULL OR actual_check_out IS NULL OR actual_check_out>=actual_check_in)
);
CREATE TABLE IF NOT EXISTS visit_participants (
 id SERIAL PRIMARY KEY, tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 visit_id INTEGER NOT NULL REFERENCES visits(id) ON DELETE CASCADE,
 participant_type VARCHAR(40) NOT NULL, reference_id INTEGER,
 display_name VARCHAR(200), is_primary BOOLEAN NOT NULL DEFAULT FALSE,
 participant_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
 created_at TIMESTAMP NOT NULL DEFAULT NOW(),
 CONSTRAINT ck_visit_participant_type CHECK(participant_type IN
 ('LEAD','CHANNEL_PARTNER','CUSTOMER','USER','ORGANISATION','OTHER')),
 CONSTRAINT ck_visit_participant_identity CHECK(reference_id IS NOT NULL OR display_name IS NOT NULL)
);
CREATE TABLE IF NOT EXISTS visit_tags (
 id SERIAL PRIMARY KEY, tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 visit_id INTEGER NOT NULL REFERENCES visits(id) ON DELETE CASCADE,
 tag VARCHAR(80) NOT NULL, created_at TIMESTAMP NOT NULL DEFAULT NOW(),
 CONSTRAINT uq_visit_tag UNIQUE(visit_id,tag)
);
CREATE TABLE IF NOT EXISTS visit_attachments (
 id SERIAL PRIMARY KEY, tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 visit_id INTEGER NOT NULL REFERENCES visits(id) ON DELETE CASCADE,
 file_name VARCHAR(250) NOT NULL, mime_type VARCHAR(120),
 storage_reference VARCHAR(500) NOT NULL,
 attachment_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
 created_by INTEGER NOT NULL REFERENCES users(id),
 created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_visit_types_tenant_order
 ON visit_type_configurations(tenant_id,display_order);
CREATE INDEX IF NOT EXISTS ix_visit_statuses_tenant_order
 ON visit_status_configurations(tenant_id,display_order);
CREATE INDEX IF NOT EXISTS ix_visits_tenant_status_arrival
 ON visits(tenant_id,status_key,expected_arrival);
CREATE INDEX IF NOT EXISTS ix_visits_tenant_location_active
 ON visits(tenant_id,location_id,is_active);
CREATE INDEX IF NOT EXISTS ix_visits_tenant_type
 ON visits(tenant_id,visit_type_key);
CREATE INDEX IF NOT EXISTS ix_visits_lead ON visits(lead_id);
CREATE INDEX IF NOT EXISTS ix_visits_project ON visits(project_id);
CREATE INDEX IF NOT EXISTS ix_visits_assigned_user ON visits(assigned_user_id);
CREATE INDEX IF NOT EXISTS ix_visit_participants_visit ON visit_participants(visit_id);
CREATE INDEX IF NOT EXISTS ix_visit_participants_tenant_type_ref
 ON visit_participants(tenant_id,participant_type,reference_id);
CREATE INDEX IF NOT EXISTS ix_visit_tags_visit ON visit_tags(visit_id);
CREATE INDEX IF NOT EXISTS ix_visit_attachments_visit ON visit_attachments(visit_id);
"""


def _guard(url):
    actual = (urlparse(url).hostname or '').lower()
    expected = (os.getenv('EXPECTED_DATABASE_HOST') or '').strip().lower()
    if not expected or actual != expected:
        raise SystemExit('ERROR: DATABASE_URL host does not match EXPECTED_DATABASE_HOST.')


def _state(cur):
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema()")
    present = {row[0] for row in cur.fetchall()}
    return {'present': sorted(TABLES & present), 'missing': sorted(TABLES - present)}


def _seed(cur):
    cur.execute('SELECT id FROM tenants')
    tenant_ids = [row[0] for row in cur.fetchall()]
    for tenant_id in tenant_ids:
        for key, name, order, colour in VISIT_TYPES:
            cur.execute(
                """INSERT INTO visit_type_configurations
                   (tenant_id,internal_key,display_name,display_order,colour)
                   VALUES(%s,%s,%s,%s,%s)
                   ON CONFLICT(tenant_id,internal_key) DO NOTHING""",
                (tenant_id, key, name, order, colour),
            )
        for key, name, order, colour, terminal in VISIT_STATUSES:
            cur.execute(
                """INSERT INTO visit_status_configurations
                   (tenant_id,internal_key,display_name,display_order,colour,is_terminal)
                   VALUES(%s,%s,%s,%s,%s,%s)
                   ON CONFLICT(tenant_id,internal_key) DO NOTHING""",
                (tenant_id, key, name, order, colour, terminal),
            )
    for key, action in [('visits.view', 'VIEW'), ('visits.manage', 'MANAGE')]:
        cur.execute(
            """INSERT INTO permission_definitions(key,module,action,description)
               VALUES(%s,'visits',%s,%s) ON CONFLICT(key) DO NOTHING""",
            (key, action, f'{action.title()} visits'),
        )
    cur.execute(
        """INSERT INTO role_permissions
           (tenant_id,business_role_id,permission_id,scope_type,effect)
           SELECT br.tenant_id,br.id,p.id,
             CASE WHEN br.key='PLATFORM_OWNER' THEN 'PLATFORM' ELSE 'TENANT' END,'ALLOW'
           FROM business_roles br JOIN permission_definitions p
             ON p.key IN('visits.view','visits.manage')
           WHERE br.key IN('PLATFORM_OWNER','ADMIN') ON CONFLICT DO NOTHING"""
    )
    for role, scope in (
        ('SALES_MANAGER', 'TEAM'), ('RELATIONSHIP_MANAGER', 'OWN'),
        ('RECEPTION', 'TENANT'),
    ):
        cur.execute(
            """INSERT INTO role_permissions
               (tenant_id,business_role_id,permission_id,scope_type,effect)
               SELECT br.tenant_id,br.id,p.id,%s,'ALLOW'
               FROM business_roles br JOIN permission_definitions p
                 ON p.key IN('visits.view','visits.manage')
               WHERE br.key=%s AND br.tenant_id IS NOT NULL
               ON CONFLICT DO NOTHING""",
            (scope, role),
        )


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    url = get_database_url()
    _guard(url)
    with psycopg2.connect(url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout='30s'")
            print(f'Before: {_state(cursor)}')
            if args.apply:
                cursor.execute(DDL)
                _seed(cursor)
                after = _state(cursor)
                if after['missing']:
                    raise RuntimeError(after)
                print(f'After: {after}')
        connection.commit()


if __name__ == '__main__':
    main()
