"""
Migration script: copies all data from local SQLite → Neon PostgreSQL.
Wipes existing Neon data first, then inserts SQLite data preserving IDs.
"""
import os, sqlite3, sys

DATABASE_URL = os.environ.get('DATABASE_URL', '')
if not DATABASE_URL:
    print("Paste your Neon connection string and press Enter:")
    DATABASE_URL = input("DATABASE_URL: ").strip()
if not DATABASE_URL:
    print("No connection string provided. Exiting."); sys.exit(1)

# Normalise postgres:// → postgresql://
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

print(f"Connecting to Neon: {DATABASE_URL[:60]}...")

import psycopg2
from psycopg2.extras import execute_values

pg = psycopg2.connect(DATABASE_URL)
pg.autocommit = False
pgc = pg.cursor()

# ── Read SQLite ────────────────────────────────────────────────────────────────
sl = sqlite3.connect('instance/mvp.db')
sl.row_factory = sqlite3.Row
slc = sl.cursor()

def rows(table, cols, bool_cols=None):
    slc.execute(f"SELECT {', '.join(cols)} FROM {table} ORDER BY id")
    result = []
    for r in slc.fetchall():
        row = list(r)
        if bool_cols:
            for i in bool_cols:
                row[i] = bool(row[i]) if row[i] is not None else None
        result.append(tuple(row))
    return result

print("Reading SQLite data...")

roles_data = rows('roles', ['id','name','display_name','permissions'])
users_data = rows('users', ['id','name','email','phone','password_hash','role','manager_id','assigned_manager_id','is_active','created_at','last_login'], bool_cols=[8])
projects_data = rows('projects', ['id','name','description','location','developer','project_type','budget_min','budget_max','is_active','created_by','created_at','updated_at'], bool_cols=[8])
leads_data = rows('leads', ['id','name','phone','email','source','budget_min','budget_max','project_id','status','assigned_to','assigned_by','sales_manager_id','created_by','created_at','updated_at','is_active'], bool_cols=[15])
status_hist_data = rows('status_history', ['id','lead_id','old_status','new_status','changed_by','changed_at'])
lead_notes_data = rows('lead_notes', ['id','lead_id','note','created_by','created_at'])
assign_hist_data = rows('lead_assignment_history', ['id','lead_id','assigned_from','assigned_to','assigned_by','reason','assigned_at'])
activity_data = rows('activity_logs', ['id','user_id','action','module','resource_id','resource_type','old_value','new_value','description','ip_address','device_info','created_at'])

print(f"  roles: {len(roles_data)}, users: {len(users_data)}, projects: {len(projects_data)}, leads: {len(leads_data)}")
print(f"  status_history: {len(status_hist_data)}, lead_notes: {len(lead_notes_data)}, assign_history: {len(assign_hist_data)}, activity_logs: {len(activity_data)}")

sl.close()

# ── Wipe Neon tables (in FK-safe order) ───────────────────────────────────────
print("\nClearing Neon tables...")
for tbl in ['activity_logs','lead_assignment_history','lead_notes','status_history','leads','projects','users','roles']:
    pgc.execute(f'DELETE FROM {tbl}')
    print(f"  cleared {tbl}")
pg.commit()

# ── Insert helper ──────────────────────────────────────────────────────────────
def insert(table, cols, data):
    if not data:
        return
    placeholders = ','.join(['%s'] * len(cols))
    col_str = ','.join(cols)
    execute_values(pgc, f"INSERT INTO {table} ({col_str}) VALUES %s ON CONFLICT DO NOTHING", data)
    print(f"  inserted {len(data)} rows into {table}")

# ── Insert data ────────────────────────────────────────────────────────────────
print("\nInserting data into Neon...")

insert('roles', ['id','name','display_name','permissions'], roles_data)
insert('users', ['id','name','email','phone','password_hash','role','manager_id','assigned_manager_id','is_active','created_at','last_login'], users_data)
insert('projects', ['id','name','description','location','developer','project_type','budget_min','budget_max','is_active','created_by','created_at','updated_at'], projects_data)
insert('leads', ['id','name','phone','email','source','budget_min','budget_max','project_id','status','assigned_to','assigned_by','sales_manager_id','created_by','created_at','updated_at','is_active'], leads_data)
insert('status_history', ['id','lead_id','old_status','new_status','changed_by','changed_at'], status_hist_data)
insert('lead_notes', ['id','lead_id','note','created_by','created_at'], lead_notes_data)
insert('lead_assignment_history', ['id','lead_id','assigned_from','assigned_to','assigned_by','reason','assigned_at'], assign_hist_data)
insert('activity_logs', ['id','user_id','action','module','resource_id','resource_type','old_value','new_value','description','ip_address','device_info','created_at'], activity_data)

pg.commit()

# ── Reset PostgreSQL sequences so new inserts get correct IDs ──────────────────
print("\nResetting sequences...")
for tbl in ['roles','users','projects','leads','status_history','lead_notes','lead_assignment_history','activity_logs']:
    pgc.execute(f"SELECT setval(pg_get_serial_sequence('{tbl}', 'id'), COALESCE((SELECT MAX(id) FROM {tbl}), 0) + 1, false)")
    print(f"  reset sequence for {tbl}")

pg.commit()
pg.close()

print("\n✅ Migration complete! All your data is now in Neon PostgreSQL.")
