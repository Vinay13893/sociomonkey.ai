"""Additive: grant visits.view/visits.manage at TENANT scope to Sales
Manager and Relationship Manager business roles.

list_visits/create_visit (app/routes/visits.py) both require TENANT scope
via @require_capability(..., 'TENANT'). _scope_matches only satisfies a
TENANT-scope request with a TENANT (or PLATFORM) grant - a TEAM or OWN
grant never ranks high enough (see app/services/permissions.py:_scope_
matches). Phase 2's original seed gave RELATIONSHIP_MANAGER only an OWN
grant and SALES_MANAGER no visits.* grant at all, so the existing
"Visit" button on a Channel Partner's profile has always 403'd for both
roles - only Admin/Platform Owner (blanket '*') and Reception (already
TENANT-scoped) could actually use it. Idempotent - safe to re-run.
"""
import argparse
import os
import sys
from urllib.parse import urlparse

import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db_safety import get_database_url


def _host_guard(url):
    actual = (urlparse(url).hostname or '').lower()
    expected = (os.environ.get('EXPECTED_DATABASE_HOST') or '').strip().lower()
    if not expected or actual != expected:
        raise SystemExit('ERROR: DATABASE_URL host does not match required EXPECTED_DATABASE_HOST.')


def _seed(cur):
    cur.execute("""INSERT INTO role_permissions(tenant_id,business_role_id,permission_id,scope_type,effect)
                   SELECT br.tenant_id,br.id,p.id,'TENANT','ALLOW'
                   FROM business_roles br CROSS JOIN permission_definitions p
                   WHERE br.key IN ('SALES_MANAGER','RELATIONSHIP_MANAGER')
                     AND p.key IN ('visits.view','visits.manage') AND br.tenant_id IS NOT NULL
                   ON CONFLICT DO NOTHING""")


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
            cur.execute("""SELECT br.key, p.key, COUNT(*) FROM role_permissions rp
                           JOIN business_roles br ON br.id=rp.business_role_id
                           JOIN permission_definitions p ON p.id=rp.permission_id
                           WHERE p.key IN ('visits.view','visits.manage')
                             AND br.key IN ('SALES_MANAGER','RELATIONSHIP_MANAGER')
                             AND rp.scope_type='TENANT'
                           GROUP BY br.key, p.key""")
            print(f'Before: {cur.fetchall()}')
            if args.apply:
                _seed(cur)
                cur.execute("""SELECT br.key, p.key, COUNT(*) FROM role_permissions rp
                               JOIN business_roles br ON br.id=rp.business_role_id
                               JOIN permission_definitions p ON p.id=rp.permission_id
                               WHERE p.key IN ('visits.view','visits.manage')
                                 AND br.key IN ('SALES_MANAGER','RELATIONSHIP_MANAGER')
                                 AND rp.scope_type='TENANT'
                               GROUP BY br.key, p.key""")
                print(f'After: {cur.fetchall()}')
        conn.commit()


if __name__ == '__main__':
    main()
