import { api, loadMe, status } from "/platform-static/auth.js";

const message = document.querySelector("#logoutStatus");
await loadMe();
document.querySelector("#confirmLogout").addEventListener("click", async () => {
  try {
    await api("/api/v1/auth/logout", { method: "POST" });
    location.assign("/login");
  } catch (error) { status(message, error.message, "error"); }
});
document.querySelector("#cancelLogout").addEventListener("click", () => location.assign("/platform-account"));
