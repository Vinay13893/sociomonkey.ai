import sqlite3, bcrypt, os, sys

db = os.path.join(os.path.dirname(__file__), "instance", "mvp.db")
conn = sqlite3.connect(db)
c    = conn.cursor()

email = "gangarealty.lms@gmail.com"
r = c.execute("SELECT id, email, tenant_id FROM users WHERE email=?", (email,)).fetchone()
if r:
    print("Test user already exists:", r)
else:
    pw_hash = bcrypt.hashpw(b"LmsAdmin@2024", bcrypt.gensalt()).decode()
    # Get the ganga tenant id
    tenant = c.execute("SELECT id FROM tenants WHERE slug='ganga'").fetchone()
    tenant_id = tenant[0] if tenant else None
    c.execute(
        "INSERT INTO users (name, email, password_hash, role, tenant_id, is_active, created_at)"
        " VALUES (?, ?, ?, ?, ?, 1, datetime('now'))",
        ("LMS Test Admin", email, pw_hash, "tenant_admin", tenant_id),
    )
    conn.commit()
    r = c.execute("SELECT id, email, role, tenant_id FROM users WHERE email=?", (email,)).fetchone()
    print("Created test user:", r)

conn.close()
