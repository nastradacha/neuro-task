#!/usr/bin/env python3
import sqlite3
import os

def migrate_db(db_path='tasks.db'):
    """
    A simple migration script for NeuroTask's SQLite database.
    It checks for and creates new columns (like 'category' or 'sort_order').
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # 1) Add 'category' column if missing
    #    category is a TEXT column (e.g., "Work", "Personal")
    try:
        c.execute("ALTER TABLE tasks ADD COLUMN category TEXT")
        print("Added 'category' column to 'tasks'.")
    except sqlite3.OperationalError:
        print("'category' column already exists, skipping...")

    # 2) Add 'sort_order' column if missing
    #    used for manual drag-and-drop ordering
    try:
        c.execute("ALTER TABLE tasks ADD COLUMN sort_order INTEGER DEFAULT 0")
        print("Added 'sort_order' column to 'tasks'.")
    except sqlite3.OperationalError:
        print("'sort_order' column already exists, skipping...")

    conn.commit()
    conn.close()
    print("Database migration complete!")

if __name__ == '__main__':
    # Adjust 'tasks.db' path if your DB file is in a different location
    migrate_db(db_path='tasks.db')
