import psycopg2

from db_safety import get_database_url


DATABASE_URL = get_database_url()
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

cur.execute('SELECT COUNT(*) FROM leads')
print('Total leads:', cur.fetchone()[0])

print('\nSample phones (id, name, phone):')
cur.execute('SELECT id, name, phone FROM leads ORDER BY id LIMIT 20')
for r in cur.fetchall():
    print(r)

print('\nDuplicate phones:')
cur.execute('''
    SELECT phone, COUNT(*) as cnt, array_agg(id ORDER BY id) as ids
    FROM leads WHERE phone IS NOT NULL AND phone != \'\'
    GROUP BY phone HAVING COUNT(*) > 1 ORDER BY cnt DESC
''')
rows = cur.fetchall()
if rows:
    for r in rows:
        print(r)
else:
    print('  None')

conn.close()
