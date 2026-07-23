"""Additive Phase 3 tenant business-configuration foundation."""
import argparse
import os
import sys
from urllib.parse import urlparse

import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db_safety import get_database_url

TABLES = {'lead_status_configurations','lead_source_configurations','business_rule_configurations'}

DDL = """
ALTER TABLE activity_logs ADD COLUMN IF NOT EXISTS correlation_id VARCHAR(36);
CREATE INDEX IF NOT EXISTS ix_activity_logs_correlation_id ON activity_logs(correlation_id);
CREATE TABLE IF NOT EXISTS lead_status_configurations (
 id SERIAL PRIMARY KEY, tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 internal_key VARCHAR(80) NOT NULL, display_name VARCHAR(120) NOT NULL,
 display_order INTEGER NOT NULL DEFAULT 0, colour VARCHAR(20) NOT NULL DEFAULT '#64748b',
 is_active BOOLEAN NOT NULL DEFAULT TRUE, pipeline_group VARCHAR(80),
 is_qualified BOOLEAN NOT NULL DEFAULT FALSE, is_lost BOOLEAN NOT NULL DEFAULT FALSE,
 is_terminal BOOLEAN NOT NULL DEFAULT FALSE, visibility VARCHAR(20) NOT NULL DEFAULT 'VISIBLE',
 updated_by INTEGER REFERENCES users(id), created_at TIMESTAMP NOT NULL DEFAULT NOW(),
 updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
 CONSTRAINT uq_status_config_tenant_key UNIQUE(tenant_id,internal_key)
);
CREATE TABLE IF NOT EXISTS lead_source_configurations (
 id SERIAL PRIMARY KEY, tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 lead_source_id INTEGER NOT NULL REFERENCES lead_sources(id),
 display_name VARCHAR(200) NOT NULL, display_order INTEGER NOT NULL DEFAULT 0,
 is_active BOOLEAN NOT NULL DEFAULT TRUE, reporting_group VARCHAR(120),
 project_id INTEGER REFERENCES projects(id), manager_id INTEGER REFERENCES users(id),
 visibility VARCHAR(20) NOT NULL DEFAULT 'VISIBLE', updated_by INTEGER REFERENCES users(id),
 created_at TIMESTAMP NOT NULL DEFAULT NOW(), updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
 CONSTRAINT uq_source_config_tenant_source UNIQUE(tenant_id,lead_source_id)
);
CREATE TABLE IF NOT EXISTS business_rule_configurations (
 id SERIAL PRIMARY KEY, tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 rule_key VARCHAR(100) NOT NULL, display_name VARCHAR(160) NOT NULL,
 version INTEGER NOT NULL DEFAULT 1, definition JSONB NOT NULL DEFAULT '{}'::jsonb,
 is_active BOOLEAN NOT NULL DEFAULT TRUE, effective_from TIMESTAMP NOT NULL DEFAULT NOW(),
 effective_to TIMESTAMP, created_by INTEGER REFERENCES users(id),
 created_at TIMESTAMP NOT NULL DEFAULT NOW(),
 CONSTRAINT uq_business_rule_version UNIQUE(tenant_id,rule_key,version)
);
CREATE INDEX IF NOT EXISTS ix_status_config_tenant ON lead_status_configurations(tenant_id);
CREATE INDEX IF NOT EXISTS ix_source_config_tenant ON lead_source_configurations(tenant_id);
CREATE INDEX IF NOT EXISTS ix_business_rules_tenant_key_active ON business_rule_configurations(tenant_id,rule_key,is_active);
"""

STATUSES = [
 ('new','New','#3b82f6','NEW',False,False,False), ('no_answer','No Answer','#f59e0b','CONTACT',False,False,False),
 ('follow_up','Follow Up','#8b5cf6','CONTACT',False,False,False), ('callback_scheduled','Callback Scheduled','#6366f1','CONTACT',False,False,False),
 ('interested','Interested','#10b981','QUALIFIED',True,False,False), ('site_visit_planned','Site Visit Planned','#06b6d4','QUALIFIED',True,False,False),
 ('site_visit_done','Site Visit Done','#14b8a6','ADVANCED',True,False,False), ('negotiation','Negotiation','#eab308','ADVANCED',True,False,False),
 ('booking_done','Booking Done','#22c55e','CLOSED',True,False,True), ('not_interested','Not Interested','#64748b','CLOSED',False,True,True),
 ('lost','Lost','#ef4444','CLOSED',False,True,True), ('junk','Junk','#78716c','CLOSED',False,True,True),
]
RULES = {
 'warm_lead': {'status_in':['interested','site_visit_planned']},
 'hot_lead': {'status_in':['site_visit_done','negotiation']},
 'cold_lead': {'status_in':['new','no_answer']},
 'sla': {'minutes':30}, 'escalation': {'overdue_minutes':60},
 'callback_ageing': {'warning_minutes':10},
 'priority': {'status_weights':{'hot':100,'warm':50,'cold':10}},
}


def guard(url):
    if (urlparse(url).hostname or '').lower() != (os.getenv('EXPECTED_DATABASE_HOST') or '').lower():
        raise SystemExit('ERROR: DATABASE_URL host does not match EXPECTED_DATABASE_HOST.')


def state(cur):
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema()")
    present={r[0] for r in cur.fetchall()}
    return {'present':sorted(TABLES & present),'missing':sorted(TABLES-present)}


def seed(cur):
    import json
    for order, row in enumerate(STATUSES):
        key,name,colour,group,qualified,lost,terminal=row
        cur.execute("""INSERT INTO lead_status_configurations
          (tenant_id,internal_key,display_name,display_order,colour,pipeline_group,is_qualified,is_lost,is_terminal)
          SELECT id,%s,%s,%s,%s,%s,%s,%s,%s FROM tenants ON CONFLICT DO NOTHING""",
          (key,name,order,colour,group,qualified,lost,terminal))
    cur.execute("""INSERT INTO lead_source_configurations
      (tenant_id,lead_source_id,display_name,display_order,is_active,reporting_group,manager_id)
      SELECT tenant_id,id,name,row_number() OVER(PARTITION BY tenant_id ORDER BY id)-1,is_active,source_type,assign_manager_id
      FROM lead_sources ON CONFLICT DO NOTHING""")
    for key, definition in RULES.items():
        cur.execute("""INSERT INTO business_rule_configurations
          (tenant_id,rule_key,display_name,version,definition)
          SELECT id,%s,%s,1,%s::jsonb FROM tenants ON CONFLICT DO NOTHING""",
          (key,key.replace('_',' ').title(),json.dumps(definition)))
    for key, action in [('configuration.view','VIEW'),('configuration.manage','MANAGE')]:
        cur.execute("""INSERT INTO permission_definitions(key,module,action,description)
                       VALUES(%s,'configuration',%s,%s) ON CONFLICT(key) DO NOTHING""",
                    (key,action,f'{action.title()} tenant configuration'))
    cur.execute("""INSERT INTO role_permissions(tenant_id,business_role_id,permission_id,scope_type,effect)
      SELECT br.tenant_id,br.id,p.id,CASE WHEN br.key='PLATFORM_OWNER' THEN 'PLATFORM' ELSE 'TENANT' END,'ALLOW'
      FROM business_roles br JOIN permission_definitions p ON p.key IN('configuration.view','configuration.manage')
      WHERE br.key IN('PLATFORM_OWNER','ADMIN') ON CONFLICT DO NOTHING""")


def main():
    p=argparse.ArgumentParser(); m=p.add_mutually_exclusive_group(required=True)
    m.add_argument('--check',action='store_true'); m.add_argument('--apply',action='store_true'); args=p.parse_args()
    url=get_database_url(); guard(url)
    with psycopg2.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout='30s'"); print(f'Before: {state(cur)}')
            if args.apply:
                cur.execute(DDL); seed(cur); after=state(cur)
                if after['missing']: raise RuntimeError(after)
                print(f'After: {after}')
        conn.commit()


if __name__ == '__main__':
    main()
