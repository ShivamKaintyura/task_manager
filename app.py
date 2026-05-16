import os
import sqlite3
from datetime import date
from functools import wraps

from flask import Flask, jsonify, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "team-task-manager-dev-key")

DATABASE = "task_manager.db"
VALID_ROLES = {"admin", "member"}
VALID_STATUSES = {"pending", "completed"}


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def normalize(value):
    return (value or "").strip().lower()


def row_to_dict(row):
    return dict(row) if row else None


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin', 'member'))
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        created_by INTEGER NOT NULL,
        FOREIGN KEY (created_by) REFERENCES users(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('pending', 'completed')),
        project_id INTEGER NOT NULL,
        assigned_to INTEGER NOT NULL,
        deadline TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(id),
        FOREIGN KEY (assigned_to) REFERENCES users(id)
    )
    """)

    cursor.execute("UPDATE users SET role = lower(trim(role)) WHERE role IS NOT NULL")
    cursor.execute("UPDATE tasks SET status = lower(trim(status)) WHERE status IS NOT NULL")
    conn.commit()
    conn.close()


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None

    conn = get_db()
    user = conn.execute(
        "SELECT id, name, email, role FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    return row_to_dict(user)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            return jsonify({"message": "Login required"}), 401
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user:
            return jsonify({"message": "Login required"}), 401
        if user["role"] != "admin":
            return jsonify({"message": "Admin access required"}), 403
        return view(*args, **kwargs)

    return wrapped


@app.route("/")
def signup_page():
    return render_template("signup.html")


@app.route("/login-page")
def login_page():
    return render_template("login.html")


@app.route("/dashboard-page")
def dashboard_page():
    return render_template("dashboard.html")


@app.route("/signup", methods=["POST"])
def signup():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    email = normalize(data.get("email"))
    password = data.get("password") or ""
    role = normalize(data.get("role")) or "member"

    if not name or not email or not password:
        return jsonify({"message": "Name, email and password are required"}), 400
    if role not in VALID_ROLES:
        return jsonify({"message": "Role must be admin or member"}), 400

    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
            (name, email, generate_password_hash(password), role),
        )
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
    except sqlite3.IntegrityError:
        return jsonify({"message": "Email already exists"}), 409

    return jsonify({
        "message": "User registered successfully",
        "user": {"id": user_id, "name": name, "email": email, "role": role},
    }), 201


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = normalize(data.get("email"))
    password = data.get("password") or ""

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()

    password_matches = False
    if user and user["password"]:
        stored_password = user["password"]
        if stored_password.startswith(("scrypt:", "pbkdf2:", "argon2:")):
            password_matches = check_password_hash(stored_password, password)
        else:
            password_matches = stored_password == password

    if not user or not password_matches:
        return jsonify({"message": "Invalid credentials"}), 401

    session["user_id"] = user["id"]
    session["role"] = normalize(user["role"])

    return jsonify({
        "message": "Login successful",
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "role": normalize(user["role"]),
        },
    })


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})


@app.route("/me", methods=["GET"])
@login_required
def me():
    return jsonify({"user": current_user()})


@app.route("/users", methods=["GET"])
@login_required
def get_users():
    conn = get_db()
    users = conn.execute(
        "SELECT id, name, email, role FROM users ORDER BY name COLLATE NOCASE"
    ).fetchall()
    conn.close()
    return jsonify({"users": [row_to_dict(user) for user in users]})


@app.route("/projects", methods=["GET"])
@login_required
def get_projects():
    conn = get_db()
    projects = conn.execute("""
        SELECT projects.id, projects.name, projects.created_by, users.name AS owner_name
        FROM projects
        LEFT JOIN users ON users.id = projects.created_by
        ORDER BY projects.id DESC
    """).fetchall()
    conn.close()
    return jsonify({"projects": [row_to_dict(project) for project in projects]})


@app.route("/projects", methods=["POST"])
@admin_required
def create_project():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    created_by = current_user()["id"]

    if not name:
        return jsonify({"message": "Project name is required"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO projects (name, created_by) VALUES (?, ?)",
        (name, created_by),
    )
    conn.commit()
    project_id = cursor.lastrowid
    conn.close()

    return jsonify({
        "message": "Project created successfully",
        "project": {"id": project_id, "name": name, "created_by": created_by},
    }), 201


@app.route("/tasks", methods=["POST"])
@admin_required
def create_task():
    data = request.get_json() or {}
    title = (data.get("title") or "").strip()
    status = normalize(data.get("status")) or "pending"
    project_id = data.get("project_id")
    assigned_to = data.get("assigned_to")
    deadline = (data.get("deadline") or "").strip()

    if not title or not project_id or not assigned_to or not deadline:
        return jsonify({"message": "Title, project, assignee and deadline are required"}), 400
    if status not in VALID_STATUSES:
        return jsonify({"message": "Status must be pending or completed"}), 400

    conn = get_db()
    project = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
    user = conn.execute("SELECT id FROM users WHERE id = ?", (assigned_to,)).fetchone()
    if not project:
        conn.close()
        return jsonify({"message": "Project does not exist"}), 400
    if not user:
        conn.close()
        return jsonify({"message": "Assignee does not exist"}), 400

    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO tasks (title, status, project_id, assigned_to, deadline)
        VALUES (?, ?, ?, ?, ?)
        """,
        (title, status, project_id, assigned_to, deadline),
    )
    conn.commit()
    task_id = cursor.lastrowid
    conn.close()

    return jsonify({
        "message": "Task created and assigned successfully",
        "task": {
            "id": task_id,
            "title": title,
            "status": status,
            "project_id": project_id,
            "assigned_to": assigned_to,
            "deadline": deadline,
        },
    }), 201


@app.route("/tasks", methods=["GET"])
@login_required
def get_tasks():
    user = current_user()
    conn = get_db()

    query = """
        SELECT tasks.id, tasks.title, tasks.status, tasks.project_id, tasks.assigned_to,
               tasks.deadline, projects.name AS project_name, users.name AS assignee_name
        FROM tasks
        LEFT JOIN projects ON projects.id = tasks.project_id
        LEFT JOIN users ON users.id = tasks.assigned_to
    """
    params = ()
    if user["role"] != "admin":
        query += " WHERE tasks.assigned_to = ?"
        params = (user["id"],)
    query += " ORDER BY tasks.deadline ASC, tasks.id DESC"

    tasks = conn.execute(query, params).fetchall()
    conn.close()

    return jsonify({"tasks": [row_to_dict(task) for task in tasks]})


@app.route("/tasks/<int:id>", methods=["PUT"])
@login_required
def update_task(id):
    data = request.get_json() or {}
    new_status = normalize(data.get("status"))

    if new_status not in VALID_STATUSES:
        return jsonify({"message": "Status must be pending or completed"}), 400

    user = current_user()
    conn = get_db()
    task = conn.execute("SELECT * FROM tasks WHERE id = ?", (id,)).fetchone()

    if not task:
        conn.close()
        return jsonify({"message": "Task not found"}), 404
    if user["role"] != "admin" and task["assigned_to"] != user["id"]:
        conn.close()
        return jsonify({"message": "You can only update your assigned tasks"}), 403

    conn.execute("UPDATE tasks SET status = ? WHERE id = ?", (new_status, id))
    conn.commit()
    conn.close()

    return jsonify({"message": "Task status updated"})


@app.route("/dashboard", methods=["GET"])
@login_required
def dashboard():
    user = current_user()
    conn = get_db()

    where = ""
    params = []
    if user["role"] != "admin":
        where = "WHERE assigned_to = ?"
        params.append(user["id"])

    total_tasks = conn.execute(
        f"SELECT COUNT(*) FROM tasks {where}",
        params,
    ).fetchone()[0]
    completed_tasks = conn.execute(
        f"SELECT COUNT(*) FROM tasks {where} {'AND' if where else 'WHERE'} lower(status) = 'completed'",
        params,
    ).fetchone()[0]
    pending_tasks = conn.execute(
        f"SELECT COUNT(*) FROM tasks {where} {'AND' if where else 'WHERE'} lower(status) = 'pending'",
        params,
    ).fetchone()[0]
    overdue_tasks = conn.execute(
        f"""
        SELECT COUNT(*) FROM tasks
        {where} {'AND' if where else 'WHERE'} lower(status) != 'completed'
        AND date(deadline) < date(?)
        """,
        [*params, date.today().isoformat()],
    ).fetchone()[0]

    conn.close()

    return jsonify({
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "pending_tasks": pending_tasks,
        "overdue_tasks": overdue_tasks,
    })


init_db()


if __name__ == "__main__":
    app.run(debug=True)
