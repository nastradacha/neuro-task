import sqlite3

conn = sqlite3.connect('tasks.db')
c = conn.cursor()

# Create subtasks table if it doesn’t already exist
c.execute('''
    CREATE TABLE IF NOT EXISTS subtasks (
        id INTEGER PRIMARY KEY,
        parent_task_id INTEGER NOT NULL,
        subtask TEXT NOT NULL,
        completed BOOLEAN DEFAULT 0,
        FOREIGN KEY (parent_task_id) REFERENCES tasks(id)
    )
''')

conn.commit()
conn.close()
