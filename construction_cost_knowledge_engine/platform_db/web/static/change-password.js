import { api, loadMe, status } from "/platform-static/auth.js";
import { requestedNext } from "/platform-static/navigation.js";

const form = document.querySelector("#changePasswordForm");
const message = document.querySelector("#changePasswordStatus");
const me = await loadMe();
if (!me.user.must_change_password) location.replace(requestedNext());

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = form.querySelector("button[type=submit]");
  button.disabled = true;
  try {
    await api("/api/v1/auth/change-password", {
      method: "POST",
      body: JSON.stringify({
        current_password: form.current_password.value,
        new_password: form.new_password.value,
      }),
    });
    form.reset();
    status(message, "密码已修改，正在进入审核工作台。", "success");
    location.replace(requestedNext());
  } catch (error) {
    status(message, error.message, "error");
  } finally {
    button.disabled = false;
  }
});
