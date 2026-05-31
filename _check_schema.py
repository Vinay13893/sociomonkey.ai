import sqlite3
db = "instance/mvp.db"
conn = sqlite3.connect(db)
c = conn.cursor()
tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Tables:", tables)
for t in ["users", "otp_codes", "otp_tokens", "tenants"]:
    if t in tables:
        cols = [r[1] for r in c.execute(f"PRAGMA table_info({t})").fetchall()]
        print(f"  {t}: {cols}")
    else:
        print(f"  {t}: MISSING")
conn.close()
