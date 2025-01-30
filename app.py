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
    conn = get_db()
    c = conn.cursor()
    c.execute('INSERT INTO tasks (task, due_date, priority) VALUES (?, ?, ?)',
             (data['task'], data['due_date'], data.get('priority', 'medium')))
    conn.commit()
    return jsonify({'status': 'success'}), 201

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
    
@app.route('/tasks/<int:task_id>/complete', methods=['PATCH'])
def toggle_completion(task_id):
    conn = get_db()
    data = request.json
    c = conn.cursor()
    c.execute('UPDATE tasks SET completed = ? WHERE id = ?',
             (data['completed'], task_id))
    conn.commit()
    return jsonify({'status': 'success'})



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
