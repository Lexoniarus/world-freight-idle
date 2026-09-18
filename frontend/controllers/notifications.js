/** Own persistent map notices and transient game notifications. */
export class Notifications {
  /** @param {HTMLElement} toast
   * @param {HTMLElement} mapNotice
   * @param {Pick<typeof globalThis, "setTimeout" | "clearTimeout">} [timers]
   */
  constructor(toast, mapNotice, timers = globalThis) {
    this.toast = toast;
    this.mapNotice = mapNotice;
    this.timers = timers;
    this.timer = null;
    this.show = this.show.bind(this);
  }
  /** Show literal text in the appropriate notification surface.
   * @param {string} message
   * @param {string} [kind]
   */
  show(message, kind = "game") {
    if (kind === "map") {
      this.mapNotice.textContent = message;
      this.mapNotice.hidden = false;
      return;
    }
    this.toast.textContent = message;
    this.toast.classList.add("visible");
    this.timers.clearTimeout(this.timer);
    this.timer = this.timers.setTimeout(() => this.toast.classList.remove("visible"), 6500);
  }
  /** Stop a pending dismissal. */
  destroy() {
    this.timers.clearTimeout(this.timer);
  }
}
