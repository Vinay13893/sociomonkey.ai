import sqlite3
conn = sqlite3.connect('instance/mvp.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
for (t,) in cur.fetchall():
    cols = [c[1] for c in cur.execute(f'PRAGMA table_info({t})').fetchall()]
    print(f"{t}: {cols}")
conn.close()
