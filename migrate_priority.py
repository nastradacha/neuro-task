import sqlite3

conn = sqlite3.connect('tasks.db')
c = conn.cursor()

# Add priority column if not exists
try:
    c.execute("ALTER TABLE tasks ADD COLUMN priority TEXT CHECK(priority IN ('low', 'medium', 'high')) DEFAULT 'medium'")
except sqlite3.OperationalError:
    pass  # Column already exists

# Update existing records
c.execute("UPDATE tasks SET priority = 'medium' WHERE priority IS NULL")
conn.commit()
conn.close()