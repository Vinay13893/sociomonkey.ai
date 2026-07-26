"""Additive: grant the reports.export capability to Sales Manager and
Calling Manager business roles at TEAM scope.

Phase 2 seeded reports.view for these roles but never reports.export,
leaving no non-Admin role able to export the Operational Analytics report
even though they could already view it. Idempotent - safe to re-run.

Production note: this grant was applied live via the app's own db.session
(the temporary /api/_internal/phase13i-fixups-20260726 route), not by
running this script directly against DATABASE_URL - see the phase13
outage postmortem (commit ece4cc9) for why a local script's DATABASE_URL
cannot be trusted to match what Vercel's backend actually connects to.
This file exists for fresh environments (dev/staging/CI) where running it
directly is safe.
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
                   SELECT br.tenant_id,br.id,p.id,'TEAM','ALLOW'
                   FROM business_roles br CROSS JOIN permission_definitions p
                   WHERE br.key IN ('SALES_MANAGER','CALLING_MANAGER')
                     AND p.key='reports.export' AND br.tenant_id IS NOT NULL
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
            cur.execute("""SELECT br.key, COUNT(*) FROM role_permissions rp
                           JOIN business_roles br ON br.id=rp.business_role_id
                           JOIN permission_definitions p ON p.id=rp.permission_id
                           WHERE p.key='reports.export' AND br.key IN ('SALES_MANAGER','CALLING_MANAGER')
                           GROUP BY br.key""")
            print(f'Before: {cur.fetchall()}')
            if args.apply:
                _seed(cur)
                cur.execute("""SELECT br.key, COUNT(*) FROM role_permissions rp
                               JOIN business_roles br ON br.id=rp.business_role_id
                               JOIN permission_definitions p ON p.id=rp.permission_id
                               WHERE p.key='reports.export' AND br.key IN ('SALES_MANAGER','CALLING_MANAGER')
                               GROUP BY br.key""")
                print(f'After: {cur.fetchall()}')
        conn.commit()


if __name__ == '__main__':
    main()
