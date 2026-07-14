"""
Migration: google_foundation_phase1_20260613
==========================================
Adds:
- connected_google_ads_accounts child table
- attribution tracking columns on leads and ingested_lead_logs

Run:
  cd backend
  python migrations/google_foundation_phase1_20260613.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import inspect, text

from app import create_app, db
from db_safety import guard_sqlalchemy_engine


def _add_column_if_missing(table_name, column_name, sql_def):
    inspector = inspect(db.engine)
    columns = {col['name'] for col in inspector.get_columns(table_name)}
    if column_name in columns:
        print(f'{table_name}.{column_name} already exists')
        return
    db.session.execute(text(f'ALTER TABLE {table_name} ADD COLUMN {sql_def}'))
    print(f'Added {table_name}.{column_name}')


def _create_indexes_if_needed(index_sql_statements):
    for sql in index_sql_statements:
        db.session.execute(text(sql))


def main():
    app = create_app()
    with app.app_context():
        engine = db.engine
        guard_sqlalchemy_engine(engine)
        dialect = engine.dialect.name

        # 1) Multi-account child table
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS connected_google_ads_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                source_id INTEGER NOT NULL,
                customer_id VARCHAR(32) NOT NULL,
                customer_name VARCHAR(255),
                resource_name VARCHAR(128),
                metadata_json JSON,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_google_ads_account_per_source UNIQUE (tenant_id, source_id, customer_id)
            )
        """))

        _create_indexes_if_needed([
            "CREATE INDEX IF NOT EXISTS ix_google_ads_accounts_tenant_source_active ON connected_google_ads_accounts (tenant_id, source_id, is_active)",
            "CREATE INDEX IF NOT EXISTS ix_google_ads_accounts_source_id ON connected_google_ads_accounts (source_id)",
        ])

        # 2) leads attribution fields
        _add_column_if_missing('leads', 'gclid', 'gclid VARCHAR(255)')
        _add_column_if_missing('leads', 'utm_source', 'utm_source VARCHAR(255)')
        _add_column_if_missing('leads', 'utm_medium', 'utm_medium VARCHAR(255)')
        _add_column_if_missing('leads', 'utm_campaign', 'utm_campaign VARCHAR(255)')
        _add_column_if_missing('leads', 'utm_content', 'utm_content VARCHAR(255)')
        _add_column_if_missing('leads', 'utm_term', 'utm_term VARCHAR(255)')
        _add_column_if_missing('leads', 'landing_page_url', 'landing_page_url TEXT')

        # 3) ingestion log attribution fields
        _add_column_if_missing('ingested_lead_logs', 'gclid', 'gclid VARCHAR(255)')
        _add_column_if_missing('ingested_lead_logs', 'utm_source', 'utm_source VARCHAR(255)')
        _add_column_if_missing('ingested_lead_logs', 'utm_medium', 'utm_medium VARCHAR(255)')
        _add_column_if_missing('ingested_lead_logs', 'utm_campaign', 'utm_campaign VARCHAR(255)')
        _add_column_if_missing('ingested_lead_logs', 'utm_content', 'utm_content VARCHAR(255)')
        _add_column_if_missing('ingested_lead_logs', 'utm_term', 'utm_term VARCHAR(255)')
        _add_column_if_missing('ingested_lead_logs', 'landing_page_url', 'landing_page_url TEXT')

        # 4) indexes for attribution lookup
        _create_indexes_if_needed([
            "CREATE INDEX IF NOT EXISTS ix_leads_gclid ON leads (gclid)",
            "CREATE INDEX IF NOT EXISTS ix_leads_utm_source ON leads (utm_source)",
            "CREATE INDEX IF NOT EXISTS ix_leads_utm_medium ON leads (utm_medium)",
            "CREATE INDEX IF NOT EXISTS ix_leads_utm_campaign ON leads (utm_campaign)",
            "CREATE INDEX IF NOT EXISTS ix_leads_utm_content ON leads (utm_content)",
            "CREATE INDEX IF NOT EXISTS ix_leads_utm_term ON leads (utm_term)",
            "CREATE INDEX IF NOT EXISTS ix_ingested_logs_gclid ON ingested_lead_logs (gclid)",
            "CREATE INDEX IF NOT EXISTS ix_ingested_logs_utm_source ON ingested_lead_logs (utm_source)",
            "CREATE INDEX IF NOT EXISTS ix_ingested_logs_utm_medium ON ingested_lead_logs (utm_medium)",
            "CREATE INDEX IF NOT EXISTS ix_ingested_logs_utm_campaign ON ingested_lead_logs (utm_campaign)",
            "CREATE INDEX IF NOT EXISTS ix_ingested_logs_utm_content ON ingested_lead_logs (utm_content)",
            "CREATE INDEX IF NOT EXISTS ix_ingested_logs_utm_term ON ingested_lead_logs (utm_term)",
        ])

        db.session.commit()
        print(f'Google foundation migration complete ({dialect}).')


if __name__ == '__main__':
    main()
