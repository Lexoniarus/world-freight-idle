/** Own the single animation loop; visibility and reduced motion are injected. */
export class VehicleAnimator {
  /** @param {{draw: () => void, isActive: () => boolean, isHidden: () => boolean, reducedMotion: () => boolean, requestFrame?: typeof requestAnimationFrame, cancelFrame?: typeof cancelAnimationFrame}} dependencies */
  constructor({
    draw,
    isActive,
    isHidden,
    reducedMotion,
    requestFrame = requestAnimationFrame.bind(globalThis),
    cancelFrame = cancelAnimationFrame.bind(globalThis),
  }) {
    this.draw = draw;
    this.isActive = isActive;
    this.isHidden = isHidden;
    this.reducedMotion = reducedMotion;
    this.requestFrame = requestFrame;
    this.cancelFrame = cancelFrame;
    this.frame = null;
    this.running = false;
    this.lastTick = -Infinity;
    this.tick = this.tick.bind(this);
  }
  /** Start exactly one animation chain. */
  start() {
    if (!this.running) {
      this.running = true;
      this.frame = this.requestFrame(this.tick);
    }
  }
  /** Draw at the appropriate cadence without advancing the server simulation.
   * @param {number} timestamp
   */
  tick(timestamp) {
    if (!this.running) return;
    this.frame = this.requestFrame(this.tick);
    if (
      this.isHidden() ||
      !this.isActive() ||
      timestamp - this.lastTick < (this.reducedMotion() ? 1000 : 66)
    )
      return;
    this.lastTick = timestamp;
    this.draw();
  }
  /** Cancel the loop, including callbacks already queued by a scheduler. */
  destroy() {
    this.running = false;
    if (this.frame !== null) this.cancelFrame(this.frame);
    this.frame = null;
  }
}
