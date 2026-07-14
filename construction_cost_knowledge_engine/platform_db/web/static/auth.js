let csrfToken = "";

export async function loadMe() {
  const response = await fetch("/api/v1/auth/me", { credentials: "same-origin", cache: "no-store" });
  if (response.status === 401) {
    location.assign(`/login?next=${encodeURIComponent(location.pathname)}`);
    throw new Error("authentication_required");
  }
  if (!response.ok) throw new Error("account_load_failed");
  const payload = await response.json();
  csrfToken = payload.csrf_token || "";
  return payload;
}

export async function api(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method) && !csrfToken) await loadMe();
  const headers = new Headers(options.headers || {});
  if (options.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) headers.set("X-CSRF-Token", csrfToken);
  const response = await fetch(path, { ...options, method, headers, credentials: "same-origin", cache: "no-store" });
  if (response.status === 401) {
    location.assign(`/login?next=${encodeURIComponent(location.pathname)}`);
    throw new Error("authentication_required");
  }
  const payload = response.status === 204 ? null : await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload?.detail || "request_failed");
  return payload;
}

export function setIdentity(me) {
  const target = document.querySelector("[data-identity]");
  if (target) target.textContent = `${me.user.display_name} · ${me.tenant.tenant_name}`;
}

export function status(target, message, kind = "") {
  target.textContent = message;
  target.className = `status ${kind}`.trim();
}

export function text(value) {
  return value == null ? "" : String(value);
}
