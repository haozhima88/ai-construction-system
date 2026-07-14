import { requestedNext, withNext } from "/platform-static/navigation.js";

const form = document.querySelector("form");
const message = document.querySelector("#loginStatus");
const button = form.querySelector("button[type=submit]");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  message.textContent = "";
  button.disabled = true;
  try {
    const response = await fetch("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ username: form.username.value, password: form.password.value }),
    });
    if (!response.ok) {
      message.textContent = response.status === 429 ? "Sign-in is temporarily unavailable. Try again later." : "Unable to sign in with those credentials.";
      message.className = "status error";
      return;
    }
    const payload = await response.json();
    const next = requestedNext();
    location.assign(payload.user.must_change_password ? withNext("/change-password", next) : next);
  } catch {
    message.textContent = "Sign-in service is unavailable.";
    message.className = "status error";
  } finally {
    button.disabled = false;
  }
});
