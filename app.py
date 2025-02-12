#client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# app = Flask(__name__)
# app.config["REDIS_URL"] = os.getenv("REDIS_URL", "redis://localhost:6379")
# app.register_blueprint(sse, url_prefix='/stream')

import os
import json
import sqlite3
from datetime import datetime, timedelta

from flask import Flask, render_template, request, jsonify, send_from_directory  # <-- Added send_from_directory
from flask_cors import CORS
from flask_sse import sse
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

# Initialize Flask App
app = Flask(__name__)
CORS(app)

# SSE / Redis Config
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["REDIS_URL"] = "redis://localhost:6379"
app.register_blueprint(sse, url_prefix="/stream")

# OpenAI Key will be used in AI-related routes
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def get_db():
    """
    Returns a SQLite connection with row_factory set to sqlite3.Row.
    """
    conn = sqlite3.connect('tasks.db')
    conn.row_factory = sqlite3.Row
    return conn

# -----------------------------------------------------------------------------
# INDEX ROUTE
# -----------------------------------------------------------------------------

@app.route('/')
def index():
    """Render the main index page."""
    return render_template('index.html')

# -----------------------------------------------------------------------------
# TASKS ROUTES
# -----------------------------------------------------------------------------

@app.route('/tasks', methods=['GET'])
def get_tasks():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, task, due_date, priority, completed, category, sort_order
        FROM tasks
        ORDER BY sort_order ASC, due_date
    ''')
    tasks = [dict(row) for row in cursor.fetchall()]
    return jsonify(tasks)

@app.route('/tasks', methods=['POST'])
def create_task():
    data = request.json
    task_text = (data.get('task') or '').strip()
    if not task_text:
        return jsonify({'error': 'Task description is required'}), 400

    due_date = data.get('due_date') or ''
    priority = data.get('priority', 'medium')
    category = data.get('category', '').strip()

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO tasks (task, due_date, priority, category)
        VALUES (?, ?, ?, ?)
    ''', (task_text, due_date, priority, category))
    conn.commit()

    return jsonify({'status': 'success'}), 201

@app.route('/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM subtasks WHERE parent_task_id = ?', (task_id,))
    cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    conn.commit()

    sse.publish({"message": "update"}, type='task_update')
    return jsonify({'status': 'success'})

@app.route('/tasks/<int:task_id>/complete', methods=['PATCH'])
def toggle_completion(task_id):
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE tasks
        SET completed = ?
        WHERE id = ?
    ''', (data.get('completed', False), task_id))
    conn.commit()
    return jsonify({'status': 'success'})

@app.route('/tasks/due_soon', methods=['GET'])
def get_due_tasks():
    conn = get_db()
    cursor = conn.cursor()

    now = datetime.now()
    notify_window = int(os.getenv('NOTIFICATION_WINDOW', 30))
    soon = now + timedelta(minutes=notify_window)

    cursor.execute('''
        SELECT *
        FROM tasks
        WHERE datetime(due_date) BETWEEN datetime(?) AND datetime(?)
          AND completed = 0
    ''', (now, soon))

    tasks = [dict(row) for row in cursor.fetchall()]
    return jsonify(tasks)

@app.route('/tasks/<int:task_id>', methods=['PATCH'])
def update_task(task_id):
    data = request.json
    fields = []
    values = []

    if 'task' in data:
        fields.append('task = ?')
        values.append(data['task'])
    if 'due_date' in data:
        fields.append('due_date = ?')
        values.append(data['due_date'])
    if 'priority' in data:
        fields.append('priority = ?')
        values.append(data['priority'])
    if 'category' in data:
        fields.append('category = ?')
        values.append(data['category'])

    if not fields:
        return jsonify({'error': 'No fields to update'}), 400

    query = f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?"
    values.append(task_id)

    conn = get_db()
    c = conn.cursor()
    c.execute(query, values)
    conn.commit()

    return jsonify({'status': 'success'})

@app.route('/tasks/reorder', methods=['POST'])
def reorder_tasks():
    data = request.json
    updates = data.get('updates', [])
    
    conn = get_db()
    try:
        for update in updates:
            conn.execute('''
                UPDATE tasks
                SET sort_order = ?
                WHERE id = ?
            ''', (update['sort_order'], update['id']))
        conn.commit()
        sse.publish({"message": "update"}, type='task_update')
        return jsonify({'status': 'success'})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500

# -----------------------------------------------------------------------------
# SUBTASKS ROUTES
# -----------------------------------------------------------------------------

@app.route('/tasks/<int:task_id>/subtasks', methods=['POST'])
def create_subtask(task_id):
    data = request.json
    subtask_text = (data.get('subtask') or '').strip()
    if not subtask_text:
        return jsonify({'error': 'Subtask text is required'}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO subtasks (parent_task_id, subtask)
        VALUES (?, ?)
    ''', (task_id, subtask_text))
    conn.commit()

    return jsonify({'status': 'success'}), 201

@app.route('/tasks/<int:task_id>/subtasks', methods=['GET'])
def get_subtasks(task_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM subtasks WHERE parent_task_id = ?', (task_id,))
    rows = cursor.fetchall()

    subtasks = [dict(
        id=row[0],
        parent_task_id=row[1],
        subtask=row[2],
        completed=row[3]
    ) for row in rows]
    return jsonify(subtasks)

@app.route('/tasks/<int:task_id>/subtasks/<int:subtask_id>/complete', methods=['PATCH'])
def toggle_subtask_completion(task_id, subtask_id):
    data = request.json
    completed = data.get('completed', False)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE subtasks
        SET completed = ?
        WHERE id = ? AND parent_task_id = ?
    ''', (completed, subtask_id, task_id))
    conn.commit()

    return jsonify({'status': 'success'})

@app.route('/tasks/<int:task_id>/subtasks/<int:subtask_id>', methods=['DELETE'])
def delete_subtask(task_id, subtask_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        DELETE FROM subtasks
        WHERE id = ? AND parent_task_id = ?
    ''', (subtask_id, task_id))
    conn.commit()

    return jsonify({'status': 'success'})

# -----------------------------------------------------------------------------
# AI ROUTES
# -----------------------------------------------------------------------------

@app.route('/ai/suggest', methods=['POST'])
def ai_suggest():
    data = request.json
    task_text = data.get('task', '')

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "Generate 3 suggested sub-tasks for this main task. Format as bullet points."
                },
                {
                    "role": "user",
                    "content": task_text
                }
            ]
        )
        suggestion_text = response.choices[0].message.content
        return jsonify({"suggestion": suggestion_text})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/ai/autogen', methods=['POST'])
def ai_autogen():
    data = request.json
    user_prompt = (data.get('prompt') or '').strip()
    if not user_prompt:
        return jsonify({"error": "Prompt is required"}), 400

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)

        messages = [
            {
                "role": "system",
                "content": """
You are a helpful assistant that MUST always return valid JSON with the structure:

{
  "main_task": "short phrase describing the user's main task",
  "subtasks": ["item1", "item2", "item3", ...]
}

Behavior:
1. If the user says “items needed” or “ingredients for” or "list of items needed", 
   you MUST guess typical items if not explicitly listed.
2. If the user only provides a single action with no mention of items, 
   subtasks is an empty array.
3. Remove filler phrases like "i want" or "list of items needed" from main_task.
4. Return ONLY JSON, no commentary.
"""
            },
            {"role": "user", "content": user_prompt}
        ]

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0
        )

        ai_content = response.choices[0].message.content

        try:
            parsed = json.loads(ai_content)
        except json.JSONDecodeError:
            return jsonify({
                "error": "Invalid JSON from AI",
                "raw_ai_content": ai_content
            }), 500

        return jsonify(parsed)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/sw.js')
def serve_service_worker():
    return send_from_directory('static', 'sw.js')

@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory('static', 'manifest.json')

# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
