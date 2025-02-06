import sqlite3

conn = sqlite3.connect('tasks.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS tasks
             (id INTEGER PRIMARY KEY,
              task TEXT,
              due_date TEXT,
              priority TEXT CHECK(priority IN ('low', 'medium', 'high')) DEFAULT 'medium',
              completed BOOLEAN DEFAULT 0,
              category TEXT,
              sort_order INTEGER DEFAULT 0)''')
conn.commit()
conn.close()