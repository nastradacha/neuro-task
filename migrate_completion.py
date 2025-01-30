import sqlite3

conn = sqlite3.connect('tasks.db')
c = conn.cursor()

try:
    c.execute("ALTER TABLE tasks ADD COLUMN completed BOOLEAN DEFAULT 0")
except sqlite3.OperationalError:
    pass  # Column exists already

c.execute("UPDATE tasks SET completed = 0 WHERE completed IS NULL")
conn.commit()
conn.close()