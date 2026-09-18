import { renderAuth } from "../views/auth.js";
import { requiredElement } from "../ui/dom.js";
import { icon } from "../ui/illustrations.js";

/** Own authentication mode, form submission and event cleanup. */
export class AuthController {
  /** @param {HTMLElement} root
   * @param {import("../api.js").GameApiClient} api
   * @param {import('../types.js').Navigate} redirect */
  constructor(root, api, redirect) {
    this.root = root;
    this.api = api;
    this.redirect = redirect;
    this.registering = false;
    this.disposed = false;
    this.listeners = new AbortController();
  }
  /** Mount the authentication view and attach its controls. */
  start() {
    this.root.replaceChildren(renderAuth());
    const options = { signal: this.listeners.signal };
    requiredElement("#login-tab").addEventListener("click", () => this.setMode(false), options);
    requiredElement("#register-tab").addEventListener("click", () => this.setMode(true), options);
    requiredElement("#auth-form").addEventListener(
      "submit",
      (event) => {
        event.preventDefault();
        void this.submitCredentials();
      },
      options,
    );
  }
  /** Present login or registration without replacing the form.
   * @param {boolean} registering
   */
  setMode(registering) {
    this.registering = registering;
    for (const [id, active] of [
      ["login-tab", !registering],
      ["register-tab", registering],
    ]) {
      const tab = requiredElement("#" + id);
      tab.classList.toggle("active", Boolean(active));
      tab.setAttribute("aria-pressed", String(active));
    }
    requiredElement("#form-title").textContent = registering
      ? "Dein Netzwerk beginnt."
      : "Willkommen zurück.";
    requiredElement("#form-help").textContent = registering
      ? "Dein Spielername erscheint öffentlich in der Rangliste."
      : "Melde dich an und bring deine Flotte auf Kurs.";
    requiredElement("#password").setAttribute(
      "autocomplete",
      registering ? "new-password" : "current-password",
    );
    requiredElement("#submit-auth").replaceChildren(
      registering ? "Konto erstellen & losfahren " : "Anmelden ",
      icon("arrow", 18),
    );
    requiredElement("#auth-status").textContent = "";
  }
  /** Prevent mode changes and duplicate submissions while authenticating.
   * @param {boolean} busy
   */
  setBusy(busy) {
    for (const id of ["submit-auth", "login-tab", "register-tab"])
      requiredElement("#" + id).toggleAttribute("disabled", busy);
  }
  /** Submit credentials exclusively to the same-origin API. */
  async submitCredentials() {
    this.setBusy(true);
    requiredElement("#auth-status").textContent = "Bitte warten …";
    const form = /** @type {HTMLFormElement} */ (requiredElement("#auth-form"));
    try {
      await this.api.request(this.registering ? "/auth/register" : "/auth/login", {
        method: "POST",
        body: JSON.stringify(Object.fromEntries(new FormData(form))),
      });
      if (!this.disposed) this.redirect("/");
    } catch (error) {
      if (this.disposed) return;
      requiredElement("#auth-status").textContent = error.message;
      this.setBusy(false);
    }
  }
  /** Release handlers and abort an in-flight authentication request. */
  destroy() {
    this.disposed = true;
    this.listeners.abort();
    this.api.destroy();
  }
}
