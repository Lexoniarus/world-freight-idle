/** Own the keyboard/click and pointer interactions for the mobile sheet. */
export class MobileSheet {
  /** @param {HTMLElement} handle
   * @param {HTMLElement} panel */
  constructor(handle, panel) {
    this.handle = handle;
    this.panel = panel;
    this.height = 60;
    this.dragStart = null;
    this.suppressClick = false;
    this.listeners = {
      click: () => this.cycleHeight(),
      pointerdown: (event) => this.startDrag(event),
      pointerup: (event) => this.finishDrag(event),
      pointercancel: () => {
        this.dragStart = null;
      },
    };
  }
  /** Attach sheet controls once for the application lifetime. */
  start() {
    for (const [event, listener] of Object.entries(this.listeners))
      this.handle.addEventListener(event, listener);
  }
  /** Advance the three accessible sheet sizes. */
  cycleHeight() {
    if (this.suppressClick) {
      this.suppressClick = false;
      return;
    }
    this.setHeight(this.height === 60 ? 90 : this.height === 90 ? 25 : 60);
  }
  /** Begin a captured pointer gesture.
   * @param {PointerEvent} event
   */
  startDrag(event) {
    this.suppressClick = false;
    this.dragStart = event.clientY;
    this.handle.setPointerCapture(event.pointerId);
  }
  /** Snap a completed gesture without applying its synthetic click twice.
   * @param {PointerEvent} event
   */
  finishDrag(event) {
    if (this.dragStart === null) return;
    const distance = this.dragStart - event.clientY;
    this.dragStart = null;
    if (Math.abs(distance) <= 20) return;
    event.preventDefault();
    this.setHeight(distance > 0 ? (this.height < 60 ? 60 : 90) : this.height > 60 ? 60 : 25);
    this.suppressClick = true;
  }
  /** Apply a sheet height in dynamic viewport units.
   * @param {number} height
   */
  setHeight(height) {
    this.height = height;
    this.panel.style.setProperty("--sheet-height", height + "dvh");
  }
  /** Release pointer and click listeners. */
  destroy() {
    for (const [event, listener] of Object.entries(this.listeners))
      this.handle.removeEventListener(event, listener);
  }
}
