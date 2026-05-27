import sqlite3, json

conn = sqlite3.connect('instance/mvp.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print('=== USERS (all) ===')
cur.execute("SELECT id, name, email, role, phone, manager_id, is_active FROM users ORDER BY id")
users = [dict(r) for r in cur.fetchall()]
for u in users:
    print(u)

print('\n=== PROJECTS (all) ===')
cur.execute("SELECT id, name, location, project_type, budget_min, budget_max FROM projects ORDER BY id")
for r in cur.fetchall():
    print(dict(r))

print('\n=== LEADS (all) ===')
cur.execute("SELECT id, name, email, phone, source, status, project_id, assigned_to, created_by FROM leads ORDER BY id")
for r in cur.fetchall():
    print(dict(r))

conn.close()
print('\nDone.')
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print('Tables:', tables)

for table in tables:
    cur.execute(f"SELECT COUNT(*) FROM [{table}]")
    count = cur.fetchone()[0]
    print(f"  {table}: {count} rows")

print()
if 'user' in tables:
    cur.execute("SELECT id, name, email, role, phone, manager_id, is_active FROM [user]")
    print('=== USERS ===')
    for r in cur.fetchall():
        print(dict(r))

if 'lead' in tables:
    cur.execute("SELECT COUNT(*) FROM lead")
    print(f'\n=== LEADS: {cur.fetchone()[0]} total ===')
    cur.execute("SELECT id, name, email, phone, source, status FROM lead LIMIT 20")
    for r in cur.fetchall():
        print(dict(r))

if 'project' in tables:
    print('\n=== PROJECTS ===')
    cur.execute("SELECT id, name, location, project_type FROM project")
    for r in cur.fetchall():
        print(dict(r))

conn.close()
