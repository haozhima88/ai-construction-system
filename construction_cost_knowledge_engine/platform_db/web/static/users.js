import { api, loadMe, setIdentity, status } from "/platform-static/auth.js";

const tableBody = document.querySelector("#usersBody");
const pageStatus = document.querySelector("#pageStatus");
const createStatus = document.querySelector("#createStatus");
const resetDialog = document.querySelector("#resetDialog");
const editDialog = document.querySelector("#editDialog");
const roleDialog = document.querySelector("#roleDialog");
let users = [];
let roles = [];
let selectedUser = null;

function button(label, className, handler) {
  const item = document.createElement("button"); item.type = "button"; item.className = `button small ${className}`.trim(); item.textContent = label; item.addEventListener("click", handler); return item;
}

function showEdit(user) {
  selectedUser = user;
  editDialog.querySelector("[name=display_name]").value = user.display_name;
  editDialog.querySelector("[name=email]").value = user.email || "";
  editDialog.showModal();
}

function showReset(user) { selectedUser = user; resetDialog.querySelector("form").reset(); resetDialog.showModal(); }

function showRoles(user) {
  selectedUser = user;
  const options = roleDialog.querySelector("#roleOptions");
  options.replaceChildren(...roles.map((role) => {
    const label = document.createElement("label"); label.className = "role-option";
    const input = document.createElement("input"); input.type = "checkbox"; input.value = role.app_role_id; input.checked = user.roles.includes(role.role_code); input.dataset.roleCode = role.role_code;
    const copy = document.createElement("span");
    const strong = document.createElement("strong"); strong.textContent = role.role_name;
    const small = document.createElement("small"); small.textContent = role.permissions.join(", ");
    copy.append(strong, small); label.append(input, copy); return label;
  }));
  roleDialog.showModal();
}

function renderUsers() {
  tableBody.replaceChildren(...users.map((user) => {
    const row = document.createElement("tr");
    const values = [user.login_name, user.display_name, user.roles.join(", ") || "-", user.status, user.last_login_at ? new Date(user.last_login_at).toLocaleString() : "-"];
    values.forEach((value, index) => { const cell = document.createElement("td"); cell.textContent = value; if (index === 3) cell.className = `badge ${user.status}`; row.append(cell); });
    const actions = document.createElement("td"); actions.className = "row-actions";
    actions.append(
      button("Edit", "secondary", () => showEdit(user)),
      button("Roles", "secondary", () => showRoles(user)),
      button("Reset password", "secondary", () => showReset(user)),
      button(user.status === "active" ? "Disable" : "Enable", user.status === "active" ? "danger" : "", async () => {
        try { await api(`/api/v1/admin/users/${user.app_user_id}/${user.status === "active" ? "disable" : "enable"}`, { method: "POST" }); await loadUsers(); }
        catch (error) { status(pageStatus, error.message, "error"); }
      }),
    );
    row.append(actions); return row;
  }));
}

async function loadUsers() { const payload = await api("/api/v1/admin/users?page=1&page_size=500"); users = payload.items; renderUsers(); }

document.querySelector("#createForm").addEventListener("submit", async (event) => {
  event.preventDefault(); const form = event.currentTarget;
  try {
    await api("/api/v1/admin/users", { method: "POST", body: JSON.stringify({ username: form.username.value, display_name: form.display_name.value, email: form.email.value || null, initial_password: form.initial_password.value }) });
    form.reset(); status(createStatus, "User created. A password change is required at first sign-in.", "success"); await loadUsers();
  } catch (error) { status(createStatus, error.message, "error"); }
});

editDialog.querySelector("form").addEventListener("submit", async (event) => {
  event.preventDefault(); const form = event.currentTarget;
  await api(`/api/v1/admin/users/${selectedUser.app_user_id}`, { method: "PATCH", body: JSON.stringify({ display_name: form.display_name.value, email: form.email.value || null }) });
  editDialog.close(); await loadUsers();
});

resetDialog.querySelector("form").addEventListener("submit", async (event) => {
  event.preventDefault(); const form = event.currentTarget;
  await api(`/api/v1/admin/users/${selectedUser.app_user_id}/reset-password`, { method: "POST", body: JSON.stringify({ new_password: form.new_password.value }) });
  resetDialog.close(); status(pageStatus, "Password reset and all user sessions revoked.", "success"); await loadUsers();
});

roleDialog.querySelector("form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const checked = [...roleDialog.querySelectorAll("input[type=checkbox]")];
  for (const option of checked) {
    const had = selectedUser.roles.includes(option.dataset.roleCode);
    if (option.checked && !had) await api(`/api/v1/admin/users/${selectedUser.app_user_id}/roles`, { method: "POST", body: JSON.stringify({ role_id: option.value }) });
    if (!option.checked && had) await api(`/api/v1/admin/users/${selectedUser.app_user_id}/roles/${option.value}`, { method: "DELETE" });
  }
  roleDialog.close(); await loadUsers();
});

document.querySelectorAll("[data-close-dialog]").forEach((item) => item.addEventListener("click", () => item.closest("dialog").close()));

const me = await loadMe();
setIdentity(me);
if (!me.roles.includes("administrator")) location.assign("/platform-account");
roles = (await api("/api/v1/admin/roles")).items;
await loadUsers();
