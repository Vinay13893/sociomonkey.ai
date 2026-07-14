import psycopg2

from db_safety import get_database_url


DATABASE_URL = get_database_url()
pg = psycopg2.connect(DATABASE_URL)
cur = pg.cursor()
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
tables = [r[0] for r in cur.fetchall()]
for t in tables:
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = %s ORDER BY ordinal_position",
        (t,),
    )
    print(t, ':', [r[0] for r in cur.fetchall()])
pg.close()
