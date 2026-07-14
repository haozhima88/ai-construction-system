import { api, loadMe, setIdentity, status, text } from "/platform-static/auth.js";
import { requestedNext } from "/platform-static/navigation.js";

const accountStatus = document.querySelector("#accountStatus");
const passwordStatus = document.querySelector("#passwordStatus");
const sessionBody = document.querySelector("#sessionBody");
let me;

function renderAccount() {
  document.querySelector("#userName").textContent = me.user.display_name;
  document.querySelector("#loginName").textContent = me.user.login_name;
  document.querySelector("#tenantName").textContent = `${me.tenant.tenant_name} (${me.tenant.tenant_code})`;
  const roles = document.querySelector("#roles");
  const adminLink = document.querySelector("[data-admin-link]");
  if (adminLink) adminLink.hidden = !me.roles.includes("administrator");
  roles.replaceChildren(...me.roles.map((role) => {
    const item = document.createElement("span"); item.className = "badge active"; item.textContent = role; return item;
  }));
  if (me.user.must_change_password) status(accountStatus, "A password change is required before protected platform work can continue.", "error");
}

async function renderSessions() {
  const payload = await api("/api/v1/auth/sessions");
  sessionBody.replaceChildren(...payload.items.map((item) => {
    const row = document.createElement("tr");
    for (const value of [item.current ? "Current" : "Other", new Date(item.last_seen_at).toLocaleString(), item.client_ip || "-", item.status]) {
      const cell = document.createElement("td"); cell.textContent = text(value); row.append(cell);
    }
    const action = document.createElement("td");
    if (!item.current && item.status === "active") {
      const button = document.createElement("button"); button.className = "button danger small"; button.textContent = "Revoke";
      button.addEventListener("click", async () => { await api(`/api/v1/auth/sessions/${item.session_id}`, { method: "DELETE" }); await renderSessions(); });
      action.append(button);
    }
    row.append(action); return row;
  }));
}

document.querySelector("#passwordForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  try {
    await api("/api/v1/auth/change-password", { method: "POST", body: JSON.stringify({ current_password: form.current_password.value, new_password: form.new_password.value }) });
    form.reset(); status(passwordStatus, "Password changed. Other sessions were revoked.", "success");
    me = await loadMe(); renderAccount(); await renderSessions();
    location.assign(requestedNext());
  } catch (error) { status(passwordStatus, error.message, "error"); }
});

document.querySelector("#revokeOthers").addEventListener("click", async () => {
  const result = await api("/api/v1/auth/sessions/revoke-others", { method: "POST" });
  status(accountStatus, `${result.count} other session(s) revoked.`, "success"); await renderSessions();
});

document.querySelector("#logoutButton").addEventListener("click", () => location.assign("/logout"));

me = await loadMe();
setIdentity(me);
renderAccount();
await renderSessions();
