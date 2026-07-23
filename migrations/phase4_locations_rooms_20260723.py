"""Additive Phase 4 platform locations and lightweight meeting rooms."""
import argparse
import os
import re
import sys
from urllib.parse import urlparse

import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db_safety import get_database_url

TABLES = {'tenant_brands','locations','project_locations','meeting_rooms'}

DDL = """
CREATE TABLE IF NOT EXISTS tenant_brands (
 id SERIAL PRIMARY KEY, tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 code VARCHAR(80) NOT NULL, name VARCHAR(160) NOT NULL,
 is_active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMP NOT NULL DEFAULT NOW(),
 CONSTRAINT uq_tenant_brand_code UNIQUE(tenant_id,code)
);
CREATE TABLE IF NOT EXISTS locations (
 id SERIAL PRIMARY KEY, tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 brand_id INTEGER REFERENCES tenant_brands(id), code VARCHAR(80) NOT NULL,
 name VARCHAR(200) NOT NULL, location_type VARCHAR(40) NOT NULL,
 address_line_1 VARCHAR(250), address_line_2 VARCHAR(250), city VARCHAR(120),
 state VARCHAR(120), country VARCHAR(120) NOT NULL DEFAULT 'India', postal_code VARCHAR(24),
 latitude NUMERIC(10,7), longitude NUMERIC(10,7),
 contact_details JSONB NOT NULL DEFAULT '{}'::jsonb,
 working_hours JSONB NOT NULL DEFAULT '{}'::jsonb, notes TEXT,
 is_active BOOLEAN NOT NULL DEFAULT TRUE, archived_at TIMESTAMP,
 created_by INTEGER REFERENCES users(id), updated_by INTEGER REFERENCES users(id),
 created_at TIMESTAMP NOT NULL DEFAULT NOW(), updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
 CONSTRAINT uq_location_tenant_code UNIQUE(tenant_id,code),
 CONSTRAINT ck_location_latitude CHECK(latitude IS NULL OR latitude BETWEEN -90 AND 90),
 CONSTRAINT ck_location_longitude CHECK(longitude IS NULL OR longitude BETWEEN -180 AND 180),
 CONSTRAINT ck_location_type CHECK(location_type IN
 ('HEAD_OFFICE','SALES_GALLERY','PROJECT_SITE','SITE_OFFICE','TEMPORARY_OFFICE','EXTERNAL_LOCATION','OTHER'))
);
CREATE TABLE IF NOT EXISTS project_locations (
 id SERIAL PRIMARY KEY, tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 project_id INTEGER NOT NULL REFERENCES projects(id), location_id INTEGER NOT NULL REFERENCES locations(id),
 relationship_type VARCHAR(40) NOT NULL DEFAULT 'SERVES',
 is_primary BOOLEAN NOT NULL DEFAULT FALSE, created_at TIMESTAMP NOT NULL DEFAULT NOW(),
 CONSTRAINT uq_project_location_relationship UNIQUE(project_id,location_id,relationship_type)
);
CREATE TABLE IF NOT EXISTS meeting_rooms (
 id SERIAL PRIMARY KEY, tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 location_id INTEGER NOT NULL REFERENCES locations(id), name VARCHAR(160) NOT NULL,
 code VARCHAR(80), capacity INTEGER NOT NULL DEFAULT 1, room_type VARCHAR(80) NOT NULL DEFAULT 'MEETING_ROOM',
 status VARCHAR(30) NOT NULL DEFAULT 'AVAILABLE', is_active BOOLEAN NOT NULL DEFAULT TRUE,
 notes TEXT, archived_at TIMESTAMP, created_by INTEGER REFERENCES users(id),
 updated_by INTEGER REFERENCES users(id), created_at TIMESTAMP NOT NULL DEFAULT NOW(),
 updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
 CONSTRAINT uq_meeting_room_location_name UNIQUE(location_id,name),
 CONSTRAINT ck_meeting_room_capacity_positive CHECK(capacity>0),
 CONSTRAINT ck_meeting_room_status CHECK(status IN
 ('AVAILABLE','OCCUPIED','RESERVED','MAINTENANCE','OUT_OF_SERVICE'))
);
CREATE INDEX IF NOT EXISTS ix_tenant_brands_tenant ON tenant_brands(tenant_id);
CREATE INDEX IF NOT EXISTS ix_locations_tenant_type_active ON locations(tenant_id,location_type,is_active);
CREATE INDEX IF NOT EXISTS ix_project_locations_project ON project_locations(project_id);
CREATE INDEX IF NOT EXISTS ix_project_locations_location ON project_locations(location_id);
CREATE INDEX IF NOT EXISTS ix_meeting_rooms_tenant_location_active ON meeting_rooms(tenant_id,location_id,is_active);
"""


def _guard(url):
    if (urlparse(url).hostname or '').lower() != (os.getenv('EXPECTED_DATABASE_HOST') or '').lower():
        raise SystemExit('ERROR: DATABASE_URL host does not match EXPECTED_DATABASE_HOST.')


def _state(cur):
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema()")
    present={row[0] for row in cur.fetchall()}
    return {'present':sorted(TABLES & present),'missing':sorted(TABLES-present)}


def _seed(cur):
    cur.execute("SELECT id,COALESCE(NULLIF(brand_name,''),name) FROM tenants")
    for tenant_id, name in cur.fetchall():
        code = re.sub(r'[^A-Z0-9]+','_',str(name).upper()).strip('_')[:80] or f'TENANT_{tenant_id}'
        cur.execute("""INSERT INTO tenant_brands(tenant_id,code,name)
                       VALUES(%s,%s,%s) ON CONFLICT(tenant_id,code) DO NOTHING""",
                    (tenant_id,code,name))
    for key, module, action in [
        ('locations.view','locations','VIEW'),('locations.manage','locations','MANAGE'),
        ('meeting_rooms.view','meeting_rooms','VIEW'),('meeting_rooms.manage','meeting_rooms','MANAGE'),
    ]:
        cur.execute("""INSERT INTO permission_definitions(key,module,action,description)
                       VALUES(%s,%s,%s,%s) ON CONFLICT(key) DO NOTHING""",
                    (key,module,action,f'{action.title()} {module.replace("_"," ")}'))
    cur.execute("""INSERT INTO role_permissions(tenant_id,business_role_id,permission_id,scope_type,effect)
      SELECT br.tenant_id,br.id,p.id,CASE WHEN br.key='PLATFORM_OWNER' THEN 'PLATFORM' ELSE 'TENANT' END,'ALLOW'
      FROM business_roles br JOIN permission_definitions p
      ON p.key IN('locations.view','locations.manage','meeting_rooms.view','meeting_rooms.manage')
      WHERE br.key IN('PLATFORM_OWNER','ADMIN') ON CONFLICT DO NOTHING""")
    cur.execute("""INSERT INTO role_permissions(tenant_id,business_role_id,permission_id,scope_type,effect)
      SELECT br.tenant_id,br.id,p.id,'TENANT','ALLOW' FROM business_roles br
      JOIN permission_definitions p ON p.key IN('locations.view','meeting_rooms.view')
      WHERE br.key IN('SALES_MANAGER','RECEPTION') AND br.tenant_id IS NOT NULL
      ON CONFLICT DO NOTHING""")


def main():
    parser=argparse.ArgumentParser(); mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check',action='store_true');mode.add_argument('--apply',action='store_true')
    args=parser.parse_args();url=get_database_url();_guard(url)
    with psycopg2.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout='30s'");print(f'Before: {_state(cur)}')
            if args.apply:
                cur.execute(DDL);_seed(cur);after=_state(cur)
                if after['missing']:raise RuntimeError(after)
                print(f'After: {after}')
        conn.commit()


if __name__=='__main__':
    main()
