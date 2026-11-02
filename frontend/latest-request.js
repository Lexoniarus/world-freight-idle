/** Own cancellation and versioning for one replaceable async request. */
export class LatestRequest {
  constructor() {
    this.version = 0;
    this.controller = null;
  }

  /** Cancel the active request and invalidate its completion.
   * @returns {void}
   */
  cancel() {
    this.controller?.abort();
    this.version++;
  }

  /** Replace the active request and expose its publication guard.
   * @returns {{signal: AbortSignal, isCurrent: () => boolean}}
   */
  start() {
    this.controller?.abort();
    this.controller = new AbortController();
    const version = ++this.version;
    return {
      signal: this.controller.signal,
      isCurrent: () => this.version === version,
    };
  }
}
