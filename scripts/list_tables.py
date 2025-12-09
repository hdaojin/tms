import sqlite3
conn = sqlite3.connect('db.sqlite3')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
print('\n'.join(r[0] for r in cur.fetchall()))
cur.close()
conn.close()
