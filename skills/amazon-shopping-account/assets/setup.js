"use strict";
(() => {
  let token = location.hash.slice(1);
  history.replaceState(null, "", location.pathname);
  const form = document.querySelector("form");
  const fields = [...form.querySelectorAll("input")];
  const buttons = [...form.querySelectorAll("button")];
  const status = document.getElementById("status");
  const clear = () => fields.forEach(field => { field.value = ""; });
  const disable = value => buttons.forEach(button => { button.disabled = value; });
  const finish = message => { clear(); token = ""; disable(true); fields.forEach(field => { field.disabled = true; }); status.textContent = message; };
  if (!/^[A-Za-z0-9_-]{43}$/.test(token)) finish("Session unavailable. Reopen setup.");
  window.addEventListener("pagehide", () => { clear(); token = ""; });
  window.addEventListener("pageshow", event => { if (event.persisted) finish("Session unavailable. Reopen setup."); });
  async function submit(action) {
    if (!token) return;
    disable(true);
    status.textContent = "";
    let credentials = {};
    if (action === "save") fields.forEach(field => { if (field.value) credentials[field.name] = field.value; });
    let body = JSON.stringify(action === "save" ? {action, credentials} : {action});
    try {
      const response = await fetch("/action", {method: "POST", mode: "same-origin", credentials: "omit", cache: "no-store", referrerPolicy: "no-referrer", headers: {"Content-Type": "application/json", "X-Setup-Token": token}, body});
      const result = await response.json();
      if (response.ok && result.status === "saved") finish("Saved. Return to your agent and say configured.");
      else if (response.ok && result.status === "later") finish("Configure later. You can return to your agent.");
      else if (response.status === 503) { status.textContent = "Could not save. Check native credential storage, then retry."; disable(false); }
      else finish("Session unavailable. Reopen setup.");
    } catch {
      finish("Save outcome unknown. Check setup status before retrying.");
    } finally {
      credentials = {}; body = "";
    }
  }
  form.addEventListener("submit", event => { event.preventDefault(); submit("save"); });
  document.getElementById("later").addEventListener("click", () => submit("later"));
})();
