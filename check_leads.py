import psycopg2

conn = psycopg2.connect(
    'postgresql://neondb_owner:npg_Z9XE7zyPvpKm@ep-cool-lab-apffph2q-pooler.c-7.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'
)
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
