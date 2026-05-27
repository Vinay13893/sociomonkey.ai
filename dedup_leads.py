import psycopg2

conn = psycopg2.connect(
    'postgresql://neondb_owner:npg_Z9XE7zyPvpKm@ep-cool-lab-apffph2q-pooler.c-7.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'
)
cur = conn.cursor()

# Find all duplicate phones (keep lowest id, delete the rest)
cur.execute('''
    SELECT phone, array_agg(id ORDER BY id) as ids
    FROM leads
    WHERE phone IS NOT NULL AND phone != \'\'
    GROUP BY phone HAVING COUNT(*) > 1
''')
rows = cur.fetchall()

total_deleted = 0
for phone, ids in rows:
    keep_id = ids[0]
    delete_ids = ids[1:]
    print(f'Phone {phone}: keeping ID {keep_id}, deleting {delete_ids}')
    cur.execute('DELETE FROM leads WHERE id = ANY(%s)', (delete_ids,))
    total_deleted += len(delete_ids)

conn.commit()
print(f'\nDeleted {total_deleted} duplicate lead(s)')

cur.execute('SELECT COUNT(*) FROM leads')
print('Total leads remaining:', cur.fetchone()[0])
conn.close()
