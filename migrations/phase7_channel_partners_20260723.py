"""Additive Phase 7 Channel Partner relationship foundation."""

import argparse
import os
import sys
from urllib.parse import urlparse

import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db_safety import get_database_url


TABLES = {
    'channel_partners',
    'channel_partner_contacts',
    'channel_partner_projects',
    'channel_partner_assignments',
    'channel_partner_notes',
}

CAPABILITIES = [
    ('channel_partners.view', 'VIEW', 'View Channel Partners'),
    ('channel_partners.create', 'CREATE', 'Create Channel Partners'),
    ('channel_partners.edit', 'EDIT', 'Edit Channel Partner profiles and notes'),
    ('channel_partners.archive', 'ARCHIVE', 'Archive and restore Channel Partners'),
    ('channel_partners.assign', 'ASSIGN', 'Assign Channel Partner relationship owners'),
    (
        'channel_partners.manage_contacts', 'MANAGE_CONTACTS',
        'Manage Channel Partner contacts',
    ),
    (
        'channel_partners.manage_projects', 'MANAGE_PROJECTS',
        'Manage Channel Partner project relationships',
    ),
    (
        'channel_partners.reveal_sensitive', 'REVEAL_SENSITIVE',
        'Reveal sensitive Channel Partner identifiers and contact details',
    ),
]

DDL = """
CREATE TABLE IF NOT EXISTS channel_partners (
 id SERIAL PRIMARY KEY,
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 code VARCHAR(80) NOT NULL,
 partner_type VARCHAR(30) NOT NULL,
 name VARCHAR(200) NOT NULL,
 organisation_name VARCHAR(240),
 gst_number VARCHAR(40),
 pan_number VARCHAR(20),
 rera_number VARCHAR(100),
 address_line_1 VARCHAR(250),
 address_line_2 VARCHAR(250),
 city VARCHAR(120),
 state VARCHAR(120),
 country VARCHAR(120) NOT NULL DEFAULT 'India',
 postal_code VARCHAR(24),
 tags JSONB NOT NULL DEFAULT '[]'::jsonb,
 notes TEXT,
 profile_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 archived_at TIMESTAMP,
 created_by INTEGER NOT NULL REFERENCES users(id),
 updated_by INTEGER NOT NULL REFERENCES users(id),
 created_at TIMESTAMP NOT NULL DEFAULT NOW(),
 updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
 CONSTRAINT uq_channel_partner_tenant_code UNIQUE(tenant_id,code),
 CONSTRAINT ck_channel_partner_type CHECK(
   partner_type IN('INDIVIDUAL','ORGANISATION')
 )
);
CREATE TABLE IF NOT EXISTS channel_partner_contacts (
 id SERIAL PRIMARY KEY,
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 channel_partner_id INTEGER NOT NULL REFERENCES channel_partners(id)
   ON DELETE CASCADE,
 name VARCHAR(200) NOT NULL,
 designation VARCHAR(120),
 mobile_numbers JSONB NOT NULL DEFAULT '[]'::jsonb,
 email_addresses JSONB NOT NULL DEFAULT '[]'::jsonb,
 is_primary BOOLEAN NOT NULL DEFAULT FALSE,
 contact_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 archived_at TIMESTAMP,
 created_by INTEGER NOT NULL REFERENCES users(id),
 updated_by INTEGER NOT NULL REFERENCES users(id),
 created_at TIMESTAMP NOT NULL DEFAULT NOW(),
 updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS channel_partner_projects (
 id SERIAL PRIMARY KEY,
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 channel_partner_id INTEGER NOT NULL REFERENCES channel_partners(id)
   ON DELETE CASCADE,
 project_id INTEGER NOT NULL REFERENCES projects(id),
 relationship_type VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
 effective_from TIMESTAMP NOT NULL DEFAULT NOW(),
 effective_to TIMESTAMP,
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 created_by INTEGER NOT NULL REFERENCES users(id),
 created_at TIMESTAMP NOT NULL DEFAULT NOW(),
 updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
 CONSTRAINT ck_channel_partner_project_type CHECK(
   relationship_type IN('PREFERRED','ACTIVE','HISTORICAL')
 )
);
CREATE TABLE IF NOT EXISTS channel_partner_assignments (
 id SERIAL PRIMARY KEY,
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 channel_partner_id INTEGER NOT NULL REFERENCES channel_partners(id)
   ON DELETE CASCADE,
 user_id INTEGER NOT NULL REFERENCES users(id),
 assignment_type VARCHAR(40) NOT NULL,
 effective_from TIMESTAMP NOT NULL DEFAULT NOW(),
 effective_to TIMESTAMP,
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 assigned_by INTEGER NOT NULL REFERENCES users(id),
 created_at TIMESTAMP NOT NULL DEFAULT NOW(),
 CONSTRAINT ck_channel_partner_assignment_type CHECK(
   assignment_type IN(
     'SALES_MANAGER','RELATIONSHIP_MANAGER','SECONDARY_RM'
   )
 )
);
CREATE TABLE IF NOT EXISTS channel_partner_notes (
 id SERIAL PRIMARY KEY,
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 channel_partner_id INTEGER NOT NULL REFERENCES channel_partners(id)
   ON DELETE CASCADE,
 content TEXT NOT NULL,
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 created_by INTEGER NOT NULL REFERENCES users(id),
 created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_channel_partners_tenant_type_active
 ON channel_partners(tenant_id,partner_type,is_active);
CREATE INDEX IF NOT EXISTS ix_channel_partner_contacts_tenant_partner_active
 ON channel_partner_contacts(tenant_id,channel_partner_id,is_active);
CREATE UNIQUE INDEX IF NOT EXISTS uq_channel_partner_primary_contact
 ON channel_partner_contacts(channel_partner_id)
 WHERE is_primary=TRUE AND is_active=TRUE;
CREATE INDEX IF NOT EXISTS ix_channel_partner_projects_tenant_project_active
 ON channel_partner_projects(tenant_id,project_id,is_active);
CREATE INDEX IF NOT EXISTS ix_channel_partner_projects_partner_active
 ON channel_partner_projects(channel_partner_id,is_active);
CREATE INDEX IF NOT EXISTS ix_channel_partner_assignments_tenant_user_active
 ON channel_partner_assignments(tenant_id,user_id,is_active);
CREATE UNIQUE INDEX IF NOT EXISTS uq_channel_partner_primary_assignment
 ON channel_partner_assignments(channel_partner_id,assignment_type)
 WHERE is_active=TRUE
   AND assignment_type IN('SALES_MANAGER','RELATIONSHIP_MANAGER');
CREATE INDEX IF NOT EXISTS ix_channel_partner_notes_partner_created
 ON channel_partner_notes(channel_partner_id,created_at DESC);
ALTER TABLE IF EXISTS notification_events
 ADD COLUMN IF NOT EXISTS channel_partner_id INTEGER
 REFERENCES channel_partners(id);
CREATE INDEX IF NOT EXISTS ix_notification_events_channel_partner
 ON notification_events(channel_partner_id)
 WHERE channel_partner_id IS NOT NULL;
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
             AND column_name='channel_partner_id'"""
    )
    notification_link = cursor.fetchone()[0]
    cursor.execute(
        """SELECT COUNT(*) FROM permission_definitions
           WHERE key LIKE 'channel_partners.%'"""
    )
    capabilities = cursor.fetchone()[0]
    return {
        'present': sorted(TABLES & present),
        'missing': sorted(TABLES - present),
        'notification_link': notification_link,
        'capabilities': capabilities,
    }


def _seed(cursor):
    for key, action, description in CAPABILITIES:
        cursor.execute(
            """INSERT INTO permission_definitions(
                 key,module,action,description
               ) VALUES(%s,'channel_partners',%s,%s)
               ON CONFLICT(key) DO NOTHING""",
            (key, action, description),
        )
    all_keys = tuple(row[0] for row in CAPABILITIES)
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
           ON CONFLICT DO NOTHING""",
        (list(all_keys),),
    )
    cursor.execute(
        """INSERT INTO role_permissions(
             tenant_id,business_role_id,permission_id,scope_type,effect
           )
           SELECT br.tenant_id,br.id,p.id,'TENANT','ALLOW'
           FROM business_roles br
           JOIN permission_definitions p ON p.key=ANY(%s)
           WHERE br.key='SALES_MANAGER' AND br.tenant_id IS NOT NULL
           ON CONFLICT DO NOTHING""",
        ([
            'channel_partners.view',
            'channel_partners.create',
            'channel_partners.edit',
            'channel_partners.archive',
            'channel_partners.assign',
            'channel_partners.manage_contacts',
            'channel_partners.manage_projects',
            'channel_partners.reveal_sensitive',
        ],),
    )
    cursor.execute(
        """INSERT INTO role_permissions(
             tenant_id,business_role_id,permission_id,scope_type,effect
           )
           SELECT br.tenant_id,br.id,p.id,'TENANT','ALLOW'
           FROM business_roles br
           JOIN permission_definitions p ON p.key=ANY(%s)
           WHERE br.key='RELATIONSHIP_MANAGER'
             AND br.tenant_id IS NOT NULL
           ON CONFLICT DO NOTHING""",
        ([
            'channel_partners.view',
            'channel_partners.edit',
            'channel_partners.manage_contacts',
            'channel_partners.manage_projects',
            'channel_partners.reveal_sensitive',
        ],),
    )
    cursor.execute(
        """INSERT INTO role_permissions(
             tenant_id,business_role_id,permission_id,scope_type,effect
           )
           SELECT br.tenant_id,br.id,p.id,'TENANT','ALLOW'
           FROM business_roles br
           JOIN permission_definitions p ON p.key=ANY(%s)
           WHERE br.key='RECEPTION' AND br.tenant_id IS NOT NULL
           ON CONFLICT DO NOTHING""",
        ([
            'channel_partners.view',
            'channel_partners.create',
            'channel_partners.manage_contacts',
        ],),
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
                if after['missing'] or after['notification_link'] != 1:
                    raise RuntimeError(after)
                print(f'After: {after}')
        connection.commit()


if __name__ == '__main__':
    main()
