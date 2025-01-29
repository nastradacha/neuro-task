import os
from flask import Flask, render_template, request, jsonify
from flask_sse import sse
import sqlite3
from datetime import datetime
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
    tasks = conn.execute('''
        SELECT *, 
        CASE WHEN datetime(due_date) < datetime('now') 
        THEN 'overdue' ELSE 'pending' END AS status
        FROM tasks 
        ORDER BY due_date
    ''').fetchall()
    return jsonify([dict(task) for task in tasks])

@app.route('/tasks', methods=['POST'])
def create_task():
    data = request.json
    conn = get_db()
    conn.execute('INSERT INTO tasks (task, due_date) VALUES (?, ?)',
                (data['task'], data['due_date']))
    conn.commit()
    sse.publish({"message": "update"}, type='task_update')
    return jsonify({'status': 'success'})

@app.route('/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    conn = get_db()
    conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
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




if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
