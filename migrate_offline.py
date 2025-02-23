import sqlite3

def migrate():
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    
    # Add sync metadata directly to tasks table
    try:
        c.execute('ALTER TABLE tasks ADD COLUMN sync_status TEXT DEFAULT "synced"')
        c.execute('ALTER TABLE tasks ADD COLUMN last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
    except sqlite3.OperationalError:
        pass  # Columns already exist
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    migrate()