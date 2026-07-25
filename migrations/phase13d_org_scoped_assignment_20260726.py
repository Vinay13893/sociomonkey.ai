"""Additive Phase 13d org-scoped auto-assignment migration.

Adds projects.organisation_unit_id (which org unit's role holders - e.g.
Calling Manager - this project's inbound leads should route to; null =
tenant-wide) and role_assignment_rotations (round-robin cursor per
tenant/role/unit pool, mirroring the existing per-form/per-source
rr_last_index columns). Purely additive; the new auto-assignment tier this
supports (app.services.ingestion_engine._resolve_calling_manager_id) is
itself dark-launched behind a FeatureFlag row that doesn't exist for any
tenant yet, so this migration changes zero live behaviour on its own.
"""
import argparse
import os
import sys
from urllib.parse import urlparse

import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db_safety import get_database_url


DDL = """
ALTER TABLE IF EXISTS projects
 ADD COLUMN IF NOT EXISTS organisation_unit_id INTEGER REFERENCES organisation_units(id);

CREATE TABLE IF NOT EXISTS role_assignment_rotations (
 id SERIAL PRIMARY KEY,
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 business_role_key VARCHAR(80) NOT NULL,
 organisation_unit_id INTEGER NOT NULL REFERENCES organisation_units(id),
 last_index INTEGER NOT NULL DEFAULT 0,
 updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
 CONSTRAINT uq_role_assignment_rotation_scope
   UNIQUE(tenant_id, business_role_key, organisation_unit_id)
);
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
        """SELECT column_name FROM information_schema.columns
           WHERE table_schema=current_schema()
             AND table_name='projects'
             AND column_name='organisation_unit_id'"""
    )
    project_columns = [row[0] for row in cursor.fetchall()]
    cursor.execute(
        """SELECT COUNT(*) FROM information_schema.tables
           WHERE table_schema=current_schema()
             AND table_name='role_assignment_rotations'"""
    )
    rotation_table = cursor.fetchone()[0]
    return {'project_columns': project_columns, 'rotation_table': rotation_table}


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
                after = _state(cursor)
                if len(after['project_columns']) != 1 or after['rotation_table'] != 1:
                    raise RuntimeError(after)
                print(f'After: {after}')
        connection.commit()


if __name__ == '__main__':
    main()
