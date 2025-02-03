import os
from flask import Flask, render_template, request, jsonify
from flask_sse import sse
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv
from openai import OpenAI
from flask_cors import CORS


load_dotenv()

#client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# app = Flask(__name__)
# app.config["REDIS_URL"] = os.getenv("REDIS_URL", "redis://localhost:6379")
# app.register_blueprint(sse, url_prefix='/stream')

app = Flask(__name__)
CORS(app)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["REDIS_URL"] = "redis://localhost:6379"
app.register_blueprint(sse, url_prefix="/stream")  # <-- This stays the same



def get_db():
    conn = sqlite3.connect('tasks.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/tasks', methods=['GET'])
def get_tasks():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id, task, due_date, priority, completed FROM tasks ORDER BY due_date')
    tasks = [dict(task) for task in c.fetchall()]
    return jsonify(tasks)

@app.route('/tasks', methods=['POST'])
def create_task():
    data = request.json
    task_text = (data.get('task') or '').strip()

    # If the task text is empty, return a 400
    if not task_text:
        return jsonify({'error': 'Task description is required'}), 400

    conn = get_db()
    c = conn.cursor()
    c.execute('INSERT INTO tasks (task, due_date, priority) VALUES (?, ?, ?)',
             (task_text, data['due_date'], data.get('priority', 'medium')))
    conn.commit()
    return jsonify({'status': 'success'}), 201

@app.route('/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    conn = get_db()
    c = conn.cursor()
    
    # Delete subtasks first
    c.execute('DELETE FROM subtasks WHERE parent_task_id = ?', (task_id,))
    
    # Delete the parent task
    c.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    
    conn.commit()
    sse.publish({"message": "update"}, type='task_update')
    return jsonify({'status': 'success'})


@app.route('/ai/suggest', methods=['POST'])
def ai_suggest():
    data = request.json
    task_text = data.get('task', '')
    
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Generate 3 suggested sub-tasks for this main task. Format as bullet points."},
                {"role": "user", "content": task_text}
            ]
        )
        return jsonify({"suggestion": response.choices[0].message.content})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/tasks/<int:task_id>/complete', methods=['PATCH'])
def toggle_completion(task_id):
    conn = get_db()
    data = request.json
    c = conn.cursor()
    c.execute('UPDATE tasks SET completed = ? WHERE id = ?',
             (data['completed'], task_id))
    conn.commit()
    return jsonify({'status': 'success'})


@app.route('/tasks/due_soon', methods=['GET'])
def get_due_tasks():
    conn = get_db()
    c = conn.cursor()
    now = datetime.now()
    #soon = now + timedelta(minutes=30)  # 30-minute warning
    soon = now + timedelta(minutes=int(os.getenv('NOTIFICATION_WINDOW', 30)))
    
    c.execute('''SELECT * FROM tasks 
               WHERE datetime(due_date) BETWEEN datetime(?) AND datetime(?)
               AND completed = 0''', 
               (now, soon))
    tasks = [dict(task) for task in c.fetchall()]
    return jsonify(tasks)



@app.route('/tasks/<int:task_id>/subtasks', methods=['POST'])
def create_subtask(task_id):
    data = request.json
    subtask_text = (data.get('subtask') or '').strip()

    if not subtask_text:
        return jsonify({'error': 'Subtask text is required'}), 400

    conn = get_db()
    c = conn.cursor()
    # Insert the subtask
    c.execute('INSERT INTO subtasks (parent_task_id, subtask) VALUES (?, ?)',
              (task_id, subtask_text))
    conn.commit()
    # Return success
    return jsonify({'status': 'success'}), 201


@app.route('/tasks/<int:task_id>/subtasks', methods=['GET'])
def get_subtasks(task_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM subtasks WHERE parent_task_id = ?', (task_id,))
    results = c.fetchall()
    # Convert each row to a dict
    subtasks = [dict(
        id=row[0],
        parent_task_id=row[1],
        subtask=row[2],
        completed=row[3]
    ) for row in results]
    return jsonify(subtasks)


@app.route('/tasks/<int:task_id>/subtasks/<int:subtask_id>/complete', methods=['PATCH'])
def toggle_subtask_completion(task_id, subtask_id):
    data = request.json
    completed = data.get('completed', False)
    
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE subtasks SET completed = ? WHERE id = ? AND parent_task_id = ?',
              (completed, subtask_id, task_id))
    conn.commit()

    return jsonify({'status': 'success'})




@app.route('/tasks/<int:task_id>/subtasks/<int:subtask_id>', methods=['DELETE'])
def delete_subtask(task_id, subtask_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM subtasks WHERE id = ? AND parent_task_id = ?', (subtask_id, task_id))
    conn.commit()

    return jsonify({'status': 'success'})





if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
