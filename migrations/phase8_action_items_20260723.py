"""Additive Phase 8 unified Action Item and Action Board configuration."""

import argparse
import os
import sys
from urllib.parse import urlparse

import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db_safety import get_database_url


TABLES = {
    'action_type_configurations',
    'action_status_configurations',
    'action_priority_configurations',
    'action_items',
}

CAPABILITIES = [
    ('action_items.view', 'VIEW', 'View permitted Action Items'),
    ('action_items.create', 'CREATE', 'Create or generate Action Items'),
    ('action_items.edit', 'EDIT', 'Edit permitted Action Items'),
    ('action_items.assign', 'ASSIGN', 'Assign and reassign Action Items'),
    ('action_items.complete', 'COMPLETE', 'Change Action Item lifecycle state'),
    ('action_items.archive', 'ARCHIVE', 'Archive and restore Action Items'),
    ('action_items.configure', 'CONFIGURE', 'Configure Action Board definitions'),
]

ACTION_TYPES = [
    ('CALL', 'Call', 10, '#2563eb', 'fa-phone', 'NORMAL'),
    ('WHATSAPP', 'WhatsApp', 20, '#16a34a', 'fa-brands fa-whatsapp', 'NORMAL'),
    ('EMAIL', 'Email', 30, '#0891b2', 'fa-envelope', 'NORMAL'),
    ('FOLLOW_UP', 'Follow-up', 40, '#7c3aed', 'fa-arrow-rotate-right', 'NORMAL'),
    ('SITE_VISIT', 'Site Visit', 50, '#ea580c', 'fa-location-dot', 'HIGH'),
    ('GALLERY_VISIT', 'Gallery Visit', 60, '#0f766e', 'fa-building', 'HIGH'),
    ('DOCUMENT_COLLECTION', 'Document Collection', 70, '#9333ea', 'fa-file-lines', 'NORMAL'),
    ('MEETING', 'Meeting', 80, '#0369a1', 'fa-people-group', 'NORMAL'),
    ('ASSIGNMENT', 'Assignment', 90, '#475569', 'fa-user-plus', 'NORMAL'),
    ('APPROVAL', 'Approval', 100, '#be123c', 'fa-circle-check', 'HIGH'),
    ('REMINDER', 'Reminder', 110, '#ca8a04', 'fa-bell', 'NORMAL'),
    ('INTERNAL_TASK', 'Internal Task', 120, '#64748b', 'fa-list-check', 'NORMAL'),
    ('OTHER', 'Other', 130, '#64748b', 'fa-ellipsis', 'NORMAL'),
]

ACTION_STATUSES = [
    ('PENDING', 'Pending', 10, '#2563eb', False),
    ('SCHEDULED', 'Scheduled', 20, '#0891b2', False),
    ('IN_PROGRESS', 'In Progress', 30, '#7c3aed', False),
    ('WAITING', 'Waiting', 40, '#ca8a04', False),
    ('COMPLETED', 'Completed', 50, '#16a34a', True),
    ('CANCELLED', 'Cancelled', 60, '#64748b', True),
    ('EXPIRED', 'Expired', 70, '#dc2626', True),
]

ACTION_PRIORITIES = [
    ('LOW', 'Low', 10, 10, '#64748b', False),
    ('NORMAL', 'Normal', 20, 20, '#2563eb', True),
    ('HIGH', 'High', 30, 30, '#ea580c', False),
    ('URGENT', 'Urgent', 40, 40, '#dc2626', False),
]

DDL = """
CREATE TABLE IF NOT EXISTS action_type_configurations (
 id SERIAL PRIMARY KEY,
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 internal_key VARCHAR(80) NOT NULL,
 display_name VARCHAR(160) NOT NULL,
 display_order INTEGER NOT NULL DEFAULT 0,
 colour VARCHAR(20) NOT NULL DEFAULT '#2563eb',
 icon VARCHAR(80),
 default_priority_key VARCHAR(40) NOT NULL DEFAULT 'NORMAL',
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 visibility VARCHAR(20) NOT NULL DEFAULT 'VISIBLE',
 updated_by INTEGER REFERENCES users(id),
 created_at TIMESTAMP NOT NULL DEFAULT NOW(),
 updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
 CONSTRAINT uq_action_type_tenant_key UNIQUE(tenant_id,internal_key)
);
CREATE TABLE IF NOT EXISTS action_status_configurations (
 id SERIAL PRIMARY KEY,
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 internal_key VARCHAR(80) NOT NULL,
 display_name VARCHAR(160) NOT NULL,
 display_order INTEGER NOT NULL DEFAULT 0,
 colour VARCHAR(20) NOT NULL DEFAULT '#64748b',
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 is_terminal BOOLEAN NOT NULL DEFAULT FALSE,
 visibility VARCHAR(20) NOT NULL DEFAULT 'VISIBLE',
 updated_by INTEGER REFERENCES users(id),
 created_at TIMESTAMP NOT NULL DEFAULT NOW(),
 updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
 CONSTRAINT uq_action_status_tenant_key UNIQUE(tenant_id,internal_key)
);
CREATE TABLE IF NOT EXISTS action_priority_configurations (
 id SERIAL PRIMARY KEY,
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 internal_key VARCHAR(40) NOT NULL,
 display_name VARCHAR(120) NOT NULL,
 display_order INTEGER NOT NULL DEFAULT 0,
 weight INTEGER NOT NULL DEFAULT 0,
 colour VARCHAR(20) NOT NULL DEFAULT '#64748b',
 is_default BOOLEAN NOT NULL DEFAULT FALSE,
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 visibility VARCHAR(20) NOT NULL DEFAULT 'VISIBLE',
 updated_by INTEGER REFERENCES users(id),
 created_at TIMESTAMP NOT NULL DEFAULT NOW(),
 updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
 CONSTRAINT uq_action_priority_tenant_key UNIQUE(tenant_id,internal_key)
);
CREATE INDEX IF NOT EXISTS ix_action_priority_tenant_default
 ON action_priority_configurations(tenant_id,is_default,is_active);
CREATE UNIQUE INDEX IF NOT EXISTS uq_action_priority_single_default
 ON action_priority_configurations(tenant_id)
 WHERE is_default=TRUE AND is_active=TRUE;
CREATE TABLE IF NOT EXISTS action_items (
 id SERIAL PRIMARY KEY,
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 source_type VARCHAR(40) NOT NULL,
 source_id INTEGER,
 action_type_key VARCHAR(80) NOT NULL,
 status_key VARCHAR(80) NOT NULL DEFAULT 'PENDING',
 priority_key VARCHAR(40) NOT NULL DEFAULT 'NORMAL',
 title VARCHAR(240) NOT NULL,
 description TEXT,
 assigned_user_id INTEGER REFERENCES users(id),
 assigned_by_user_id INTEGER REFERENCES users(id),
 organisation_unit_id INTEGER REFERENCES organisation_units(id),
 project_id INTEGER REFERENCES projects(id),
 location_id INTEGER REFERENCES locations(id),
 due_at TIMESTAMP,
 business_rule_priority INTEGER NOT NULL DEFAULT 0,
 idempotency_key VARCHAR(300),
 assigned_at TIMESTAMP,
 started_at TIMESTAMP,
 completed_at TIMESTAMP,
 cancelled_at TIMESTAMP,
 expired_at TIMESTAMP,
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 archived_at TIMESTAMP,
 created_by INTEGER NOT NULL REFERENCES users(id),
 updated_by INTEGER NOT NULL REFERENCES users(id),
 created_at TIMESTAMP NOT NULL DEFAULT NOW(),
 updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
 CONSTRAINT ck_action_item_source_type CHECK(source_type IN(
  'LEAD','VISIT','RECEPTION','CHANNEL_PARTNER','BUSINESS_RULE',
  'SLA','CALLBACK','MANUAL','AUTOMATION'
 ))
);
CREATE INDEX IF NOT EXISTS ix_action_items_tenant_assignee_status_due
 ON action_items(tenant_id,assigned_user_id,status_key,due_at);
CREATE INDEX IF NOT EXISTS ix_action_items_tenant_source
 ON action_items(tenant_id,source_type,source_id);
CREATE INDEX IF NOT EXISTS ix_action_items_tenant_unit_status
 ON action_items(tenant_id,organisation_unit_id,status_key);
CREATE UNIQUE INDEX IF NOT EXISTS uq_action_items_tenant_idempotency
 ON action_items(tenant_id,idempotency_key);
ALTER TABLE IF EXISTS notification_events
 ADD COLUMN IF NOT EXISTS action_item_id INTEGER REFERENCES action_items(id);
CREATE INDEX IF NOT EXISTS ix_notification_events_action_item
 ON notification_events(action_item_id)
 WHERE action_item_id IS NOT NULL;
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
        """SELECT table_name FROM information_schema.tables
           WHERE table_schema=current_schema()"""
    )
    present = {row[0] for row in cursor.fetchall()}
    cursor.execute(
        """SELECT COUNT(*) FROM information_schema.columns
           WHERE table_schema=current_schema()
             AND table_name='notification_events'
             AND column_name='action_item_id'"""
    )
    notification_link = cursor.fetchone()[0]
    cursor.execute(
        """SELECT COUNT(*) FROM permission_definitions
           WHERE key LIKE 'action_items.%'"""
    )
    capabilities = cursor.fetchone()[0]
    return {
        'present': sorted(TABLES & present),
        'missing': sorted(TABLES - present),
        'notification_link': notification_link,
        'capabilities': capabilities,
    }


def _seed_configurations(cursor):
    for key, name, order, colour, icon, priority in ACTION_TYPES:
        cursor.execute(
            """INSERT INTO action_type_configurations(
                 tenant_id,internal_key,display_name,display_order,colour,icon,
                 default_priority_key
               )
               SELECT id,%s,%s,%s,%s,%s,%s FROM tenants
               ON CONFLICT(tenant_id,internal_key) DO NOTHING""",
            (key, name, order, colour, icon, priority),
        )
    for key, name, order, colour, terminal in ACTION_STATUSES:
        cursor.execute(
            """INSERT INTO action_status_configurations(
                 tenant_id,internal_key,display_name,display_order,colour,
                 is_terminal
               )
               SELECT id,%s,%s,%s,%s,%s FROM tenants
               ON CONFLICT(tenant_id,internal_key) DO NOTHING""",
            (key, name, order, colour, terminal),
        )
    for key, name, order, weight, colour, is_default in ACTION_PRIORITIES:
        cursor.execute(
            """INSERT INTO action_priority_configurations(
                 tenant_id,internal_key,display_name,display_order,weight,
                 colour,is_default
               )
               SELECT id,%s,%s,%s,%s,%s,%s FROM tenants
               ON CONFLICT(tenant_id,internal_key) DO NOTHING""",
            (key, name, order, weight, colour, is_default),
        )


def _seed_permissions(cursor):
    for key, action, description in CAPABILITIES:
        cursor.execute(
            """INSERT INTO permission_definitions(
                 key,module,action,description
               ) VALUES(%s,'action_items',%s,%s)
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
                 AND rp.scope_ref_id IS NULL
                 AND rp.effect='ALLOW'
             )
           ON CONFLICT DO NOTHING""",
        (all_keys,),
    )
    manager_keys = all_keys[:-1]
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
                 AND rp.scope_ref_id IS NULL
                 AND rp.effect='ALLOW'
             )
           ON CONFLICT DO NOTHING""",
        (manager_keys,),
    )
    individual_keys = [
        'action_items.view', 'action_items.create', 'action_items.edit',
        'action_items.complete',
    ]
    cursor.execute(
        """INSERT INTO role_permissions(
             tenant_id,business_role_id,permission_id,scope_type,effect
           )
           SELECT br.tenant_id,br.id,p.id,'OWN','ALLOW'
           FROM business_roles br
           JOIN permission_definitions p ON p.key=ANY(%s)
           WHERE br.key IN(
             'CALLER','RELATIONSHIP_MANAGER','RECEPTION','LEGACY_TEAM_MEMBER'
           ) AND br.tenant_id IS NOT NULL
             AND NOT EXISTS(
               SELECT 1 FROM role_permissions rp
               WHERE rp.business_role_id=br.id
                 AND rp.permission_id=p.id
                 AND rp.scope_type='OWN'
                 AND rp.scope_ref_id IS NULL
                 AND rp.effect='ALLOW'
             )
           ON CONFLICT DO NOTHING""",
        (individual_keys,),
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
                _seed_configurations(cursor)
                _seed_permissions(cursor)
                after = _state(cursor)
                if (
                    after['missing']
                    or after['notification_link'] != 1
                    or after['capabilities'] != len(CAPABILITIES)
                ):
                    raise RuntimeError(after)
                print(f'After: {after}')
        connection.commit()


if __name__ == '__main__':
    main()
