"""
Seed/patch local SQLite instance/mvp.db for OTP local testing:
  - Create 'ganga' tenant if missing
  - Link all existing users to that tenant
"""
import sqlite3, os

db = os.path.join(os.path.dirname(__file__), "instance", "mvp.db")
conn = sqlite3.connect(db)
c    = conn.cursor()

# 1. Ensure 'ganga' tenant exists
row = c.execute("SELECT id FROM tenants WHERE slug='ganga'").fetchone()
if not row:
    c.execute("""
        INSERT INTO tenants
            (name, slug, primary_color, secondary_color, accent_color,
             plan, status, max_users, admin_email, admin_name,
             created_at, updated_at)
        VALUES
            ('Ganga Realty', 'ganga', '#1e3a5f', '#3b82f6', '#10b981',
             'enterprise', 'active', 100,
             'admin@gangarealty.com', 'Ganga Realty Admin',
             datetime('now'), datetime('now'))
    """)
    conn.commit()
    row = c.execute("SELECT id FROM tenants WHERE slug='ganga'").fetchone()
    print(f"  + tenant 'ganga' created (id={row[0]})")
else:
    print(f"  . tenant 'ganga' already exists (id={row[0]})")

tenant_id = row[0]

# 2. Link all users to this tenant (only those without a tenant)
updated = c.execute(
    "UPDATE users SET tenant_id=? WHERE tenant_id IS NULL",
    (tenant_id,)
).rowcount
conn.commit()
print(f"  + linked {updated} users to tenant_id={tenant_id}")

# 3. Print users so we know which emails to test with
print("\nUsers available for OTP testing:")
for r in c.execute("SELECT id, name, email, role FROM users ORDER BY id").fetchall():
    print(f"  [{r[0]}] {r[2]}  ({r[3]})")

conn.close()
print("\nSeed complete.")
