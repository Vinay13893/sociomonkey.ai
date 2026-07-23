"""Additive Phase 2 organisation and capability-permission foundation.

Run against the approved recovery branch first. This migration creates new
tables and seed records only; it does not alter legacy role or manager fields.
"""
import argparse
import os
import sys
from urllib.parse import urlparse

import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db_safety import get_database_url


TABLES = {
    'organisation_units', 'organisation_unit_memberships', 'business_roles',
    'user_business_roles', 'reporting_relationships', 'permission_definitions',
    'role_permissions', 'user_permission_overrides',
}

DDL = r"""
CREATE TABLE IF NOT EXISTS organisation_units (
 id SERIAL PRIMARY KEY, tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 parent_id INTEGER REFERENCES organisation_units(id), code VARCHAR(80) NOT NULL,
 name VARCHAR(160) NOT NULL, unit_type VARCHAR(50) NOT NULL DEFAULT 'GENERAL',
 description TEXT, is_active BOOLEAN NOT NULL DEFAULT TRUE,
 created_by INTEGER REFERENCES users(id), created_at TIMESTAMP NOT NULL DEFAULT NOW(),
 updated_at TIMESTAMP NOT NULL DEFAULT NOW(), CONSTRAINT uq_organisation_unit_tenant_code UNIQUE(tenant_id, code)
);
CREATE TABLE IF NOT EXISTS organisation_unit_memberships (
 id SERIAL PRIMARY KEY, tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 organisation_unit_id INTEGER NOT NULL REFERENCES organisation_units(id),
 user_id INTEGER NOT NULL REFERENCES users(id), membership_type VARCHAR(40) NOT NULL DEFAULT 'MEMBER',
 is_primary BOOLEAN NOT NULL DEFAULT FALSE, effective_from TIMESTAMP NOT NULL DEFAULT NOW(),
 effective_to TIMESTAMP, is_active BOOLEAN NOT NULL DEFAULT TRUE,
 created_by INTEGER REFERENCES users(id), created_at TIMESTAMP NOT NULL DEFAULT NOW(),
 CONSTRAINT uq_organisation_membership UNIQUE(organisation_unit_id,user_id,membership_type)
);
CREATE TABLE IF NOT EXISTS business_roles (
 id SERIAL PRIMARY KEY, tenant_id INTEGER REFERENCES tenants(id), key VARCHAR(80) NOT NULL,
 display_name VARCHAR(120) NOT NULL, description TEXT, is_system BOOLEAN NOT NULL DEFAULT FALSE,
 is_active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMP NOT NULL DEFAULT NOW(),
 updated_at TIMESTAMP NOT NULL DEFAULT NOW(), CONSTRAINT uq_business_role_tenant_key UNIQUE(tenant_id,key)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_business_role_global_key ON business_roles(key) WHERE tenant_id IS NULL;
CREATE TABLE IF NOT EXISTS user_business_roles (
 id SERIAL PRIMARY KEY, tenant_id INTEGER REFERENCES tenants(id), user_id INTEGER NOT NULL REFERENCES users(id),
 business_role_id INTEGER NOT NULL REFERENCES business_roles(id),
 organisation_unit_id INTEGER REFERENCES organisation_units(id), is_primary BOOLEAN NOT NULL DEFAULT FALSE,
 effective_from TIMESTAMP NOT NULL DEFAULT NOW(), effective_to TIMESTAMP,
 is_active BOOLEAN NOT NULL DEFAULT TRUE, assigned_by INTEGER REFERENCES users(id),
 created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_user_business_role_scope_safe
 ON user_business_roles(user_id,business_role_id,COALESCE(organisation_unit_id,0));
CREATE TABLE IF NOT EXISTS reporting_relationships (
 id SERIAL PRIMARY KEY, tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 user_id INTEGER NOT NULL REFERENCES users(id), manager_id INTEGER NOT NULL REFERENCES users(id),
 relationship_type VARCHAR(60) NOT NULL DEFAULT 'LINE_MANAGER',
 organisation_unit_id INTEGER REFERENCES organisation_units(id),
 effective_from TIMESTAMP NOT NULL DEFAULT NOW(), effective_to TIMESTAMP,
 is_primary BOOLEAN NOT NULL DEFAULT FALSE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
 created_by INTEGER REFERENCES users(id), created_at TIMESTAMP NOT NULL DEFAULT NOW(),
 updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
 CONSTRAINT ck_reporting_relationship_not_self CHECK(user_id <> manager_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_reporting_relationship_scope_safe
 ON reporting_relationships(user_id,manager_id,relationship_type,COALESCE(organisation_unit_id,0));
CREATE TABLE IF NOT EXISTS permission_definitions (
 id SERIAL PRIMARY KEY, key VARCHAR(140) NOT NULL UNIQUE, module VARCHAR(80) NOT NULL,
 action VARCHAR(50) NOT NULL, description VARCHAR(300), is_active BOOLEAN NOT NULL DEFAULT TRUE,
 created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS role_permissions (
 id SERIAL PRIMARY KEY, tenant_id INTEGER REFERENCES tenants(id),
 business_role_id INTEGER NOT NULL REFERENCES business_roles(id),
 permission_id INTEGER NOT NULL REFERENCES permission_definitions(id),
 scope_type VARCHAR(40) NOT NULL DEFAULT 'OWN', scope_ref_id VARCHAR(80),
 effect VARCHAR(10) NOT NULL DEFAULT 'ALLOW', created_by INTEGER REFERENCES users(id),
 created_at TIMESTAMP NOT NULL DEFAULT NOW(), CONSTRAINT ck_role_permission_effect CHECK(effect IN ('ALLOW','DENY'))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_role_permission_scope_safe
 ON role_permissions(business_role_id,permission_id,scope_type,COALESCE(scope_ref_id,''));
CREATE TABLE IF NOT EXISTS user_permission_overrides (
 id SERIAL PRIMARY KEY, tenant_id INTEGER REFERENCES tenants(id),
 user_id INTEGER NOT NULL REFERENCES users(id), permission_id INTEGER NOT NULL REFERENCES permission_definitions(id),
 scope_type VARCHAR(40) NOT NULL DEFAULT 'OWN', scope_ref_id VARCHAR(80), effect VARCHAR(10) NOT NULL,
 reason VARCHAR(300), effective_from TIMESTAMP NOT NULL DEFAULT NOW(), effective_to TIMESTAMP,
 is_active BOOLEAN NOT NULL DEFAULT TRUE, created_by INTEGER REFERENCES users(id),
 created_at TIMESTAMP NOT NULL DEFAULT NOW(), updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
 CONSTRAINT ck_user_permission_effect CHECK(effect IN ('ALLOW','DENY'))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_user_permission_override_scope_safe
 ON user_permission_overrides(user_id,permission_id,scope_type,COALESCE(scope_ref_id,''));
CREATE INDEX IF NOT EXISTS ix_org_units_tenant_active ON organisation_units(tenant_id,is_active);
CREATE INDEX IF NOT EXISTS ix_org_memberships_tenant_user_active ON organisation_unit_memberships(tenant_id,user_id,is_active);
CREATE INDEX IF NOT EXISTS ix_business_roles_tenant_active ON business_roles(tenant_id,is_active);
CREATE INDEX IF NOT EXISTS ix_user_business_roles_tenant_user_active ON user_business_roles(tenant_id,user_id,is_active);
CREATE INDEX IF NOT EXISTS ix_reporting_tenant_manager_active ON reporting_relationships(tenant_id,manager_id,is_active);
CREATE INDEX IF NOT EXISTS ix_permission_definitions_module ON permission_definitions(module);
CREATE INDEX IF NOT EXISTS ix_user_permission_overrides_tenant_user_active ON user_permission_overrides(tenant_id,user_id,is_active);
"""

PERMISSIONS = [
    ('organisation.view','organisation','VIEW'), ('organisation.configure','organisation','CONFIGURE'),
    ('organisation.users.create','organisation','CREATE'), ('organisation.users.edit','organisation','EDIT'),
    ('organisation.users.archive','organisation','ARCHIVE'), ('organisation.roles.assign','organisation','ASSIGN'),
    ('permissions.view','permissions','VIEW'), ('permissions.configure','permissions','CONFIGURE'),
    ('permissions.manage','permissions','MANAGE'),
    ('leads.view','leads','VIEW'), ('leads.create','leads','CREATE'), ('leads.edit','leads','EDIT'),
    ('leads.archive','leads','ARCHIVE'), ('leads.assign','leads','ASSIGN'),
    ('leads.import','leads','IMPORT'), ('leads.export','leads','EXPORT'),
    ('leads.sensitive.reveal','leads','REVEAL_SENSITIVE_DATA'),
    ('action_board.view','action_board','VIEW'), ('reports.view','reports','VIEW'),
    ('reports.export','reports','EXPORT'), ('notifications.view','notifications','VIEW'),
    ('visits.view','visits','VIEW'), ('visits.manage','visits','MANAGE'),
    ('gallery.view','gallery','VIEW'), ('gallery.manage','gallery','MANAGE'),
]

ROLE_NAMES = {
    'ADMIN':'Admin', 'CALLING_MANAGER':'Calling Manager', 'CALLER':'Caller',
    'SALES_MANAGER':'Sales Manager', 'RELATIONSHIP_MANAGER':'Relationship Manager',
    'RECEPTION':'Reception', 'LEGACY_TEAM_MEMBER':'Legacy Team Member',
}


def _host_guard(url):
    actual = (urlparse(url).hostname or '').lower()
    expected = (os.environ.get('EXPECTED_DATABASE_HOST') or '').strip().lower()
    if not expected or actual != expected:
        raise SystemExit('ERROR: DATABASE_URL host does not match required EXPECTED_DATABASE_HOST.')


def _state(cur):
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema()")
    present = {r[0] for r in cur.fetchall()}
    return {'present': sorted(TABLES & present), 'missing': sorted(TABLES - present)}


def _seed(cur):
    for key, module, action in PERMISSIONS:
        cur.execute("""INSERT INTO permission_definitions(key,module,action,description)
                       VALUES(%s,%s,%s,%s) ON CONFLICT(key) DO NOTHING""",
                    (key,module,action,f'{action.title()} {module.replace("_"," ")}'))
    cur.execute("""INSERT INTO business_roles(tenant_id,key,display_name,is_system)
                   VALUES(NULL,'PLATFORM_OWNER','Platform Owner',TRUE)
                   ON CONFLICT DO NOTHING""")
    for key, name in ROLE_NAMES.items():
        cur.execute("""INSERT INTO business_roles(tenant_id,key,display_name,is_system)
                       SELECT id,%s,%s,TRUE FROM tenants ON CONFLICT DO NOTHING""", (key,name))
    cur.execute("""INSERT INTO organisation_units(tenant_id,code,name,unit_type)
                   SELECT id,'ROOT',name,'TENANT_ROOT' FROM tenants ON CONFLICT DO NOTHING""")
    cur.execute("""INSERT INTO organisation_unit_memberships
                   (tenant_id,organisation_unit_id,user_id,membership_type,is_primary)
                   SELECT u.tenant_id,ou.id,u.id,'MEMBER',TRUE FROM users u
                   JOIN organisation_units ou ON ou.tenant_id=u.tenant_id AND ou.code='ROOT'
                   WHERE u.tenant_id IS NOT NULL ON CONFLICT DO NOTHING""")
    cur.execute("""INSERT INTO user_business_roles(tenant_id,user_id,business_role_id,organisation_unit_id,is_primary)
                   SELECT u.tenant_id,u.id,br.id,ou.id,TRUE FROM users u
                   JOIN organisation_units ou ON ou.tenant_id=u.tenant_id AND ou.code='ROOT'
                   JOIN business_roles br ON br.tenant_id=u.tenant_id AND br.key =
                     CASE u.role WHEN 'superadmin' THEN 'ADMIN' WHEN 'sales_manager' THEN 'SALES_MANAGER'
                     ELSE 'LEGACY_TEAM_MEMBER' END
                   WHERE u.tenant_id IS NOT NULL ON CONFLICT DO NOTHING""")
    cur.execute("""INSERT INTO user_business_roles(tenant_id,user_id,business_role_id,is_primary)
                   SELECT NULL,u.id,br.id,TRUE FROM users u CROSS JOIN business_roles br
                   WHERE u.role='platform_owner' AND br.tenant_id IS NULL AND br.key='PLATFORM_OWNER'
                   ON CONFLICT DO NOTHING""")
    cur.execute("""INSERT INTO reporting_relationships(tenant_id,user_id,manager_id,relationship_type,is_primary)
                   SELECT tenant_id,id,manager_id,'LEGACY_MANAGER',TRUE FROM users
                   WHERE tenant_id IS NOT NULL AND manager_id IS NOT NULL AND id<>manager_id
                   ON CONFLICT DO NOTHING""")
    cur.execute("""INSERT INTO reporting_relationships(tenant_id,user_id,manager_id,relationship_type,is_primary)
                   SELECT tenant_id,id,assigned_manager_id,'LEGACY_ASSIGNED_MANAGER',FALSE FROM users
                   WHERE tenant_id IS NOT NULL AND assigned_manager_id IS NOT NULL AND id<>assigned_manager_id
                   ON CONFLICT DO NOTHING""")
    # Bootstrap authority while legacy endpoints remain unchanged.
    cur.execute("""INSERT INTO role_permissions(tenant_id,business_role_id,permission_id,scope_type,effect)
                   SELECT br.tenant_id,br.id,p.id,
                          CASE WHEN br.key='PLATFORM_OWNER' THEN 'PLATFORM' ELSE 'TENANT' END,'ALLOW'
                   FROM business_roles br CROSS JOIN permission_definitions p
                   WHERE br.key IN ('PLATFORM_OWNER','ADMIN') ON CONFLICT DO NOTHING""")
    for role, scope, keys in [
        ('SALES_MANAGER','TEAM',['organisation.view','leads.view','leads.edit','leads.assign','action_board.view','reports.view','notifications.view']),
        ('CALLING_MANAGER','TEAM',['organisation.view','leads.view','leads.edit','leads.assign','action_board.view','reports.view','notifications.view']),
        ('CALLER','OWN',['leads.view','leads.edit','action_board.view','notifications.view']),
        ('RELATIONSHIP_MANAGER','OWN',['leads.view','leads.edit','action_board.view','notifications.view','visits.view','visits.manage']),
        ('RECEPTION','TENANT',['visits.view','visits.manage','gallery.view','gallery.manage']),
        ('LEGACY_TEAM_MEMBER','OWN',['organisation.view','leads.view','leads.edit','action_board.view','notifications.view']),
    ]:
        cur.execute("""INSERT INTO role_permissions(tenant_id,business_role_id,permission_id,scope_type,effect)
                       SELECT br.tenant_id,br.id,p.id,%s,'ALLOW' FROM business_roles br
                       JOIN permission_definitions p ON p.key=ANY(%s)
                       WHERE br.key=%s AND br.tenant_id IS NOT NULL ON CONFLICT DO NOTHING""",
                    (scope, keys, role))


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
            print(f'Before: {_state(cur)}')
            if args.apply:
                cur.execute(DDL)
                _seed(cur)
                state = _state(cur)
                if state['missing']:
                    raise RuntimeError(f'Migration validation failed: {state}')
                print(f'After: {state}')
        conn.commit()


if __name__ == '__main__':
    main()
