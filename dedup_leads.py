import psycopg2

from db_safety import get_database_url


DATABASE_URL = get_database_url(destructive=True)
conn = psycopg2.connect(DATABASE_URL)
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
