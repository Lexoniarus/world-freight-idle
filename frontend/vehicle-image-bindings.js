/** Bind rendered image nodes to shared colored assets without view requests. */
export class VehicleImageController {
  /** @param {import("./vehicle-color-assets.js").VehicleColorAssets} assets
   * @param {(callback: IntersectionObserverCallback) => IntersectionObserver | null} [observe]
   */
  constructor(
    assets,
    observe = (callback) =>
      globalThis.IntersectionObserver
        ? new IntersectionObserver(callback, { rootMargin: "200px" })
        : null,
  ) {
    this.assets = assets;
    this.bindings = new Map();
    this.disposed = false;
    this.observer = observe((entries) => {
      for (const entry of entries)
        if (entry.isIntersecting) this.load(/** @type {HTMLImageElement} */ (entry.target));
    });
  }
  /** Prepare stable identity and cached URLs before DOM comparison.
   * @param {ParentNode} root
   * @param {string} color
   */
  prepare(root, color) {
    for (const image of root.querySelectorAll(/** @type {"img"} */ ("img[data-vehicle-model]"))) {
      image.dataset.vehicleColor = color;
      const url = this.assets.peek(image.dataset.vehicleModel, image.dataset.vehicleRole, color);
      if (url) image.src = url;
    }
  }
  /** Reconcile leases; late results cannot repaint a removed or changed image.
   * @param {Iterable<HTMLImageElement>} images
   */
  update(images) {
    if (this.disposed) return;
    const active = new Set(images);
    const previous = [];
    for (const [image, binding] of this.bindings)
      if (!active.has(image) || binding.key !== this.imageKey(image)) {
        previous.push(binding.lease);
        this.observer?.unobserve(image);
        this.bindings.delete(image);
      }
    for (const image of active) {
      if (this.bindings.has(image)) continue;
      const binding = { key: this.imageKey(image), lease: null, loading: false };
      this.bindings.set(image, binding);
      const cached = this.assets.peek(
        image.dataset.vehicleModel,
        image.dataset.vehicleRole,
        image.dataset.vehicleColor,
      );
      if (this.observer && !cached) this.observer.observe(image);
      else this.load(image);
    }
    for (const lease of previous) lease?.release();
  }
  /** Acquire color only for a displayed image, preserving binding identity.
   * @param {HTMLImageElement} image
   */
  load(image) {
    const binding = this.bindings.get(image);
    if (!binding || binding.loading || this.disposed) return;
    binding.loading = true;
    this.observer?.unobserve(image);
    void this.assets
      .acquire(image.dataset.vehicleModel, image.dataset.vehicleRole, image.dataset.vehicleColor)
      .then((lease) => {
        if (this.disposed || this.bindings.get(image) !== binding) return lease.release();
        binding.lease = lease;
        image.src = lease.url;
      })
      .catch(() => {
        if (this.bindings.get(image) === binding) this.bindings.delete(image);
      });
  }
  /** @param {HTMLImageElement} image */
  imageKey(image) {
    return this.assets.key(
      image.dataset.vehicleModel,
      image.dataset.vehicleRole,
      image.dataset.vehicleColor,
    );
  }
  /** Release image leases and ignore pending bindings. */
  destroy() {
    this.disposed = true;
    this.observer?.disconnect();
    for (const binding of this.bindings.values()) binding.lease?.release();
    this.bindings.clear();
  }
}
