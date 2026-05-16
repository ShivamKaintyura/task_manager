const base = "";

const qs = (selector) => document.querySelector(selector);
const byId = (id) => document.getElementById(id);

function toast(message) {
  const toastEl = byId("toast");
  if (!toastEl) {
    alert(message);
    return;
  }

  toastEl.textContent = message;
  toastEl.classList.add("show");
  window.clearTimeout(window.toastTimer);
  window.toastTimer = window.setTimeout(() => {
    toastEl.classList.remove("show");
  }, 2600);
}

async function api(path, options = {}) {
  const res = await fetch(base + path, {
    credentials: "same-origin",
    headers: {"Content-Type": "application/json", ...(options.headers || {})},
    ...options
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.message || "Something went wrong");
  }
  return data;
}

function currentUser() {
  try {
    return JSON.parse(localStorage.getItem("taskManagerUser"));
  } catch {
    return null;
  }
}

function setCurrentUser(user) {
  localStorage.setItem("taskManagerUser", JSON.stringify(user));
}

function clearForm(ids) {
  ids.forEach((id) => {
    const el = byId(id);
    if (el) el.value = "";
  });
}

async function signup() {
  try {
    await api("/signup", {
      method: "POST",
      body: JSON.stringify({
        name: byId("name").value,
        email: byId("email").value,
        password: byId("password").value,
        role: byId("role").value
      })
    });
    toast("Signup complete. Please log in.");
    window.setTimeout(() => {
      window.location.href = "/login-page";
    }, 700);
  } catch (error) {
    toast(error.message);
  }
}

async function login() {
  try {
    const data = await api("/login", {
      method: "POST",
      body: JSON.stringify({
        email: byId("loginEmail").value,
        password: byId("loginPassword").value
      })
    });

    setCurrentUser(data.user);
    window.location.href = "/dashboard-page";
  } catch (error) {
    toast(error.message);
  }
}

async function logout() {
  await api("/logout", {method: "POST"}).catch(() => {});
  localStorage.removeItem("taskManagerUser");
  window.location.href = "/login-page";
}

async function createProject() {
  try {
    await api("/projects", {
      method: "POST",
      body: JSON.stringify({name: byId("projectName").value})
    });
    clearForm(["projectName"]);
    toast("Project created");
    await loadProjects();
  } catch (error) {
    toast(error.message);
  }
}

async function createTask() {
  try {
    await api("/tasks", {
      method: "POST",
      body: JSON.stringify({
        title: byId("taskTitle").value,
        status: byId("taskStatus").value,
        project_id: byId("projectId").value,
        assigned_to: byId("assignedTo").value,
        deadline: byId("deadline").value
      })
    });
    clearForm(["taskTitle", "deadline"]);
    byId("taskStatus").value = "pending";
    toast("Task assigned");
    await refreshDashboard();
  } catch (error) {
    toast(error.message);
  }
}

async function updateTask(id, status) {
  try {
    await api(`/tasks/${id}`, {
      method: "PUT",
      body: JSON.stringify({status})
    });
    toast("Task updated");
    await refreshDashboard();
  } catch (error) {
    toast(error.message);
  }
}

async function loadDashboard() {
  const data = await api("/dashboard");
  byId("totalTasks").innerText = data.total_tasks;
  byId("completedTasks").innerText = data.completed_tasks;
  byId("pendingTasks").innerText = data.pending_tasks;
  byId("overdueTasks").innerText = data.overdue_tasks;
}

async function loadProjects() {
  const projectSelect = byId("projectId");
  if (!projectSelect) return;

  const data = await api("/projects");
  if (!data.projects.length) {
    projectSelect.innerHTML = `<option value="">No projects yet</option>`;
    return;
  }

  projectSelect.innerHTML = data.projects
    .map((project) => `<option value="${project.id}">${project.name}</option>`)
    .join("");
}

async function loadUsers() {
  const assigneeSelect = byId("assignedTo");
  if (!assigneeSelect) return;

  const data = await api("/users");
  const members = data.users.filter((user) => user.email);
  assigneeSelect.innerHTML = members
    .map((user) => `<option value="${user.id}">${user.name || user.email} (${user.role})</option>`)
    .join("");
}

function taskRow(task) {
  const nextStatus = task.status === "completed" ? "pending" : "completed";
  const actionLabel = task.status === "completed" ? "Reopen" : "Complete";

  return `<tr>
    <td><strong>${task.title}</strong></td>
    <td>${task.project_name || `Project #${task.project_id}`}</td>
    <td>${task.assignee_name || `User #${task.assigned_to}`}</td>
    <td>${task.deadline}</td>
    <td><span class="status-pill status-${task.status}">${task.status}</span></td>
    <td>
      <button class="secondary-button" onclick="updateTask(${task.id}, '${nextStatus}')">${actionLabel}</button>
    </td>
  </tr>`;
}

async function getTasks() {
  const data = await api("/tasks");
  const taskTable = byId("taskTable");

  if (!data.tasks.length) {
    taskTable.innerHTML = `<tr><td colspan="6" class="empty-state">No tasks found</td></tr>`;
    return;
  }

  taskTable.innerHTML = data.tasks.map(taskRow).join("");
}

async function refreshDashboard() {
  await Promise.all([loadDashboard(), getTasks()]);
}

async function bootDashboard() {
  try {
    const data = await api("/me");
    setCurrentUser(data.user);

    byId("currentUserName").innerText = data.user.name || data.user.email;
    byId("currentUserRole").innerText = data.user.role;

    document.querySelectorAll(".admin-only").forEach((section) => {
      section.classList.toggle("hidden", data.user.role !== "admin");
    });

    if (data.user.role === "admin") {
      await Promise.all([loadProjects(), loadUsers()]);
    }
    await refreshDashboard();
  } catch {
    localStorage.removeItem("taskManagerUser");
    window.location.href = "/login-page";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  if (byId("taskTable")) {
    const user = currentUser();
    if (user) {
      byId("currentUserName").innerText = user.name || user.email;
      byId("currentUserRole").innerText = user.role;
    }
    bootDashboard();
  }
});
