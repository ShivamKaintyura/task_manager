# Team Task Manager

A Flask and SQLite web app for creating projects, assigning team tasks, and tracking progress with Admin and Member roles.

## Features

- Signup and login
- Admin and Member roles
- Admin-only project creation and task assignment
- Task status tracking with pending/completed states
- Member dashboard scoped to assigned tasks
- Admin dashboard for all team tasks
- Dashboard metrics for total, completed, pending, and overdue tasks
- REST API endpoints backed by SQLite relationships

## Tech Stack

- Python
- Flask
- SQLite
- HTML, CSS, JavaScript

## Run Locally

```bash
python db.py
python app.py
```

Open `http://127.0.0.1:5000` in your browser.

## REST API

- `POST /signup` - create a user
- `POST /login` - log in
- `POST /logout` - log out
- `GET /me` - current logged-in user
- `GET /users` - list users
- `GET /projects` - list projects
- `POST /projects` - create project, Admin only
- `GET /tasks` - list visible tasks
- `POST /tasks` - create and assign task, Admin only
- `PUT /tasks/<id>` - update task status
- `GET /dashboard` - task summary metrics

## Roles

Admins can create projects, assign tasks, view all tasks, and update any task status.

Members can view their assigned tasks and update the status of those tasks.
