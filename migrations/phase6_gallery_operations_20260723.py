"""Additive Phase 6 Gallery Operations status and capability seed."""

import argparse
import os
import sys
from urllib.parse import urlparse

import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db_safety import get_database_url


VISIT_STATUSES = [
    ('WAITING', 'Waiting', 25, '#d97706'),
    ('CALLED', 'Called', 27, '#0891b2'),
    ('IN_MEETING', 'In Meeting', 30, '#7c3aed'),
]

CAPABILITIES = [
    ('gallery.view', 'VIEW', 'View Gallery Operations'),
    ('gallery.check_in', 'CHECK_IN', 'Check in visits and manage the waiting queue'),
    ('gallery.check_out', 'CHECK_OUT', 'Check out visits and record no-shows'),
    ('gallery.assign', 'ASSIGN', 'Assign responsibility for gallery visits'),
    ('gallery.allocate_room', 'ALLOCATE_ROOM', 'Allocate meeting rooms to visits'),
    ('gallery.archive', 'ARCHIVE', 'Archive gallery visit records'),
    ('gallery.configure', 'CONFIGURE', 'Configure Gallery Operations'),
]


def _guard(url):
    actual = (urlparse(url).hostname or '').lower()
    expected = (os.getenv('EXPECTED_DATABASE_HOST') or '').strip().lower()
    if not expected or actual != expected:
        raise SystemExit('ERROR: DATABASE_URL host does not match EXPECTED_DATABASE_HOST.')


def _state(cur):
    cur.execute(
        """SELECT COUNT(*) FROM visit_status_configurations
           WHERE internal_key IN('WAITING','CALLED','IN_MEETING')"""
    )
    statuses = cur.fetchone()[0]
    cur.execute(
        """SELECT COUNT(*) FROM permission_definitions
           WHERE key IN(
             'gallery.view','gallery.check_in','gallery.check_out',
             'gallery.assign','gallery.allocate_room','gallery.archive',
             'gallery.configure'
           )"""
    )
    capabilities = cur.fetchone()[0]
    return {'gallery_status_rows': statuses, 'gallery_capabilities': capabilities}


def _seed(cur):
    cur.execute('SELECT id FROM tenants')
    for (tenant_id,) in cur.fetchall():
        for key, name, order, colour in VISIT_STATUSES:
            cur.execute(
                """INSERT INTO visit_status_configurations
                   (tenant_id,internal_key,display_name,display_order,colour)
                   VALUES(%s,%s,%s,%s,%s)
                   ON CONFLICT(tenant_id,internal_key) DO NOTHING""",
                (tenant_id, key, name, order, colour),
            )
    for key, action, description in CAPABILITIES:
        cur.execute(
            """INSERT INTO permission_definitions(key,module,action,description)
               VALUES(%s,'gallery',%s,%s)
               ON CONFLICT(key) DO NOTHING""",
            (key, action, description),
        )
    cur.execute(
        """INSERT INTO role_permissions
           (tenant_id,business_role_id,permission_id,scope_type,effect)
           SELECT br.tenant_id,br.id,p.id,
             CASE WHEN br.key='PLATFORM_OWNER' THEN 'PLATFORM' ELSE 'TENANT' END,
             'ALLOW'
           FROM business_roles br
           CROSS JOIN permission_definitions p
           WHERE br.key IN('PLATFORM_OWNER','ADMIN','RECEPTION')
             AND p.key IN(
               'gallery.view','gallery.check_in','gallery.check_out',
               'gallery.assign','gallery.allocate_room','gallery.archive',
               'gallery.configure'
             )
           ON CONFLICT DO NOTHING"""
    )
    cur.execute(
        """INSERT INTO role_permissions
           (tenant_id,business_role_id,permission_id,scope_type,effect)
           SELECT br.tenant_id,br.id,p.id,'TENANT','ALLOW'
           FROM business_roles br
           JOIN permission_definitions p
             ON p.key IN('gallery.view','gallery.assign')
           WHERE br.key='SALES_MANAGER' AND br.tenant_id IS NOT NULL
           ON CONFLICT DO NOTHING"""
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
                _seed(cursor)
                print(f'After: {_state(cursor)}')
        connection.commit()


if __name__ == '__main__':
    main()
