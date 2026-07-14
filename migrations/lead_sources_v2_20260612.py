"""Create Lead Sources V2 tables for form-project mapping and campaign snapshots."""

from app import create_app
from app.models.base import db
from db_safety import guard_sqlalchemy_engine


def migrate():
    app = create_app('development')
    with app.app_context():
        guard_sqlalchemy_engine(db.engine)
        sql_statements = [
            """
            CREATE TABLE IF NOT EXISTS lead_source_form_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                source_id INTEGER NOT NULL,
                source_type VARCHAR(50) NOT NULL DEFAULT 'meta',
                page_id VARCHAR(200),
                form_id VARCHAR(200) NOT NULL,
                form_name VARCHAR(500),
                project_id INTEGER NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_by INTEGER,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_form_mapping_tenant_source_form UNIQUE (tenant_id, source_id, form_id)
            )
            """,
            "CREATE INDEX IF NOT EXISTS ix_form_mapping_tenant_source_active ON lead_source_form_mappings (tenant_id, source_id, is_active)",
            """
            CREATE TABLE IF NOT EXISTS meta_campaign_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                source_id INTEGER NOT NULL,
                lead_id INTEGER,
                ingested_log_id INTEGER,
                page_id VARCHAR(200),
                form_id VARCHAR(200),
                form_name VARCHAR(500),
                campaign_id VARCHAR(200),
                campaign_name VARCHAR(500),
                campaign_status VARCHAR(100),
                campaign_objective VARCHAR(200),
                ad_set_id VARCHAR(200),
                ad_set_name VARCHAR(500),
                ad_set_status VARCHAR(100),
                optimization_goal VARCHAR(200),
                ad_id VARCHAR(200),
                ad_name VARCHAR(500),
                ad_status VARCHAR(100),
                creative_name VARCHAR(500),
                spend FLOAT,
                impressions INTEGER,
                reach INTEGER,
                clicks INTEGER,
                ctr FLOAT,
                cpc FLOAT,
                cpm FLOAT,
                frequency FLOAT,
                results INTEGER,
                cost_per_result FLOAT,
                audience VARCHAR(500),
                placement VARCHAR(500),
                age_range VARCHAR(120),
                gender VARCHAR(120),
                geo VARCHAR(200),
                extra_metrics JSON,
                snapshot_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            "CREATE INDEX IF NOT EXISTS ix_meta_snapshot_tenant_snapshot_at ON meta_campaign_snapshots (tenant_id, snapshot_at)",
            "CREATE INDEX IF NOT EXISTS ix_meta_snapshot_campaign_id ON meta_campaign_snapshots (campaign_id)",
            "CREATE INDEX IF NOT EXISTS ix_meta_snapshot_ad_set_id ON meta_campaign_snapshots (ad_set_id)",
            "CREATE INDEX IF NOT EXISTS ix_meta_snapshot_ad_id ON meta_campaign_snapshots (ad_id)",
            "CREATE INDEX IF NOT EXISTS ix_meta_snapshot_form_id ON meta_campaign_snapshots (form_id)",
        ]

        for sql in sql_statements:
            db.session.execute(db.text(sql))
        db.session.commit()
        print('Lead Sources V2 migration complete.')


if __name__ == '__main__':
    migrate()
