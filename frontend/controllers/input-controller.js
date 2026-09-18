/** Delegate shell interactions without owning game rules or rendering. */
export class InputController {
  /** @param {{page: Document, navigate: import('../types.js').Navigate, actions: import("./game-actions.js").GameActions, panel: import("./panel-controller.js").PanelController, map: import("../map/world-map.js").WorldMap | null}} dependencies */
  constructor({ page, navigate, actions, panel, map }) {
    this.page = page;
    this.navigate = navigate;
    this.actions = actions;
    this.panel = panel;
    this.map = map;
    this.listeners = new AbortController();
  }
  /** Attach one listener per interaction type. */
  start() {
    const options = { signal: this.listeners.signal };
    this.page.addEventListener("click", (event) => this.handleClick(event), options);
    this.page.addEventListener("change", (event) => this.handleChange(event), options);
    this.page.addEventListener("keydown", (event) => this.handleKey(event), options);
    this.page.addEventListener("load", (event) => this.handleImage(event, "loaded"), {
      ...options,
      capture: true,
    });
    this.page.addEventListener("error", (event) => this.handleImage(event, "failed"), {
      ...options,
      capture: true,
    });
  }
  /** Route links and action buttons, preserving modified native link clicks.
   * @param {MouseEvent} event
   */
  handleClick(event) {
    if (!(event.target instanceof Element)) return;
    const link = event.target.closest("a[data-nav]");
    if (
      link &&
      !event.ctrlKey &&
      !event.metaKey &&
      !event.shiftKey &&
      !event.altKey &&
      event.button === 0
    ) {
      event.preventDefault();
      this.navigate(link.getAttribute("href"));
    }
    const button = event.target.closest("[data-action]");
    if (button && !button.hasAttribute("disabled"))
      void this.actions.handle(
        button.getAttribute("data-action"),
        button.getAttribute("data-id") || "",
      );
  }
  /** Update a presentation preference selected by the player.
   * @param {Event} event
   */
  handleChange(event) {
    const target = event.target;
    if (!(target instanceof HTMLSelectElement) && !(target instanceof HTMLInputElement)) return;
    if (target.id === "vehicle-choice") this.actions.selectVehicle(target.value);
    if (target.dataset.layer)
      this.map?.toggle(target.dataset.layer, /** @type {HTMLInputElement} */ (target).checked);
  }
  /** Reveal loaded photos or retain their illustration after a network failure.
   * @param {Event} event
   * @param {"loaded" | "failed"} state
   */
  handleImage(event, state) {
    const image = event.target;
    if (!(image instanceof HTMLImageElement) || !image.hasAttribute("data-vehicle-photo")) return;
    const figure = image.closest(".vehicle-photo");
    if (figure instanceof HTMLElement) figure.dataset.imageState = state;
  }
  /** Close the topmost overlay using Escape and restore its focus.
   * @param {KeyboardEvent} event
   */
  handleKey(event) {
    if (event.key !== "Escape") return;
    const layers = /** @type {HTMLDetailsElement} */ (this.page.querySelector(".layer-menu"));
    if (layers.open) {
      layers.open = false;
      layers.querySelector("summary").focus();
    } else if (!this.panel.panel.hidden) this.navigate("/");
  }
  /** Remove all delegated listeners. */
  destroy() {
    this.listeners.abort();
  }
}
