import psycopg2, os
pg = psycopg2.connect(os.environ['DATABASE_URL'])
cur = pg.cursor()
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
tables = [r[0] for r in cur.fetchall()]
for t in tables:
    cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name='{t}' ORDER BY ordinal_position")
    print(t, ':', [r[0] for r in cur.fetchall()])
pg.close()
