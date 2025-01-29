import sqlite3

conn = sqlite3.connect('tasks.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS tasks
             (id INTEGER PRIMARY KEY,
              task TEXT,
              due_date TEXT,
              created_at TEXT DEFAULT CURRENT_TIMESTAMP,
              status TEXT DEFAULT 'pending')''')
conn.commit()
conn.close()