/** Own visibility-aware polling and lightweight progress updates. */
export class RefreshScheduler {
  /** @param {{refresh: () => Promise<void>, updateProgress: () => void, canRefresh: () => boolean, browser?: Window, page?: Document, timers?: typeof globalThis}} dependencies */
  constructor({
    refresh,
    updateProgress,
    canRefresh,
    browser = window,
    page = document,
    timers = globalThis,
  }) {
    this.refresh = refresh;
    this.updateProgress = updateProgress;
    this.canRefresh = canRefresh;
    this.browser = browser;
    this.page = page;
    this.timers = timers;
    this.intervals = [];
    this.poll = () => {
      if (!this.page.hidden && this.canRefresh()) void this.refresh();
    };
    this.tick = () => {
      if (!this.page.hidden) this.updateProgress();
    };
  }
  /** Start one polling loop and one progress loop. */
  start() {
    if (this.intervals.length) return;
    this.intervals = [
      this.timers.setInterval(this.poll, 10000),
      this.timers.setInterval(this.tick, 1000),
    ];
    this.page.addEventListener("visibilitychange", this.poll);
    this.browser.addEventListener("online", this.poll);
  }
  /** Release timers and browser listeners. */
  destroy() {
    this.intervals.forEach((id) => this.timers.clearInterval(id));
    this.intervals = [];
    this.page.removeEventListener("visibilitychange", this.poll);
    this.browser.removeEventListener("online", this.poll);
  }
}
