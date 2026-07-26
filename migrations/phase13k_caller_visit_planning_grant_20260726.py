"""Additive: grant gallery.view and visits.view at TENANT scope to the
CALLER business role.

Moving a Lead to "Site Visit Planned" (frontend: openSiteVisitPlanningDialog,
src/products/lms/leads.js) first loads /api/gallery-operations/references
and /api/visits/configuration to populate the form, both gated at TENANT
scope. CALLER's phase2 seed only granted leads.view/leads.edit/
action_board.view/notifications.view - no gallery.* or visits.* at all -
and the legacy 'team_member' fallback doesn't cover these either, so the
dialog 403'd before a Caller could even open the form. The actual save
(POST /api/pipeline/leads/<id>/move) already works via the team_member
legacy fallback for pipeline.move - only the two reference GETs were
blocked. Idempotent - safe to re-run.
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
                   WHERE br.key='CALLER'
                     AND p.key IN ('gallery.view','visits.view') AND br.tenant_id IS NOT NULL
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
            cur.execute("""SELECT p.key, COUNT(*) FROM role_permissions rp
                           JOIN business_roles br ON br.id=rp.business_role_id
                           JOIN permission_definitions p ON p.id=rp.permission_id
                           WHERE p.key IN ('gallery.view','visits.view')
                             AND br.key='CALLER' AND rp.scope_type='TENANT'
                           GROUP BY p.key""")
            print(f'Before: {cur.fetchall()}')
            if args.apply:
                _seed(cur)
                cur.execute("""SELECT p.key, COUNT(*) FROM role_permissions rp
                               JOIN business_roles br ON br.id=rp.business_role_id
                               JOIN permission_definitions p ON p.id=rp.permission_id
                               WHERE p.key IN ('gallery.view','visits.view')
                                 AND br.key='CALLER' AND rp.scope_type='TENANT'
                               GROUP BY p.key""")
                print(f'After: {cur.fetchall()}')
        conn.commit()


if __name__ == '__main__':
    main()
