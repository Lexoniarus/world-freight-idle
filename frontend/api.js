/** HTTP error retaining the status needed by authentication handling. */
export class ApiError extends Error {
  /** @param {string} message
   * @param {number} status */
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

/** Own backend HTTP requests and abort them when the application closes. */
export class GameApiClient {
  /** @param {typeof fetch} [fetchResponse]
   * @param {(path: string) => void} [redirect] */
  constructor(
    fetchResponse = globalThis.fetch.bind(globalThis),
    redirect = (path) => window.location.replace(path),
  ) {
    this.fetchResponse = fetchResponse;
    this.redirect = redirect;
    this.lifetime = new AbortController();
    this.request = this.request.bind(this);
    this.requestAsset = this.requestAsset.bind(this);
    this.loadFreightOffers = this.loadFreightOffers.bind(this);
    this.requestFreightRefill = this.requestFreightRefill.bind(this);
    this.loadFreightOffer = this.loadFreightOffer.bind(this);
    this.quoteFreightOffer = this.quoteFreightOffer.bind(this);
    this.dispatchFreightOffer = this.dispatchFreightOffer.bind(this);
    this.purchaseVehicle = this.purchaseVehicle.bind(this);
  }

  /** Request an API-relative resource with same-origin credentials only.
   * @param {string} path
   * @param {RequestInit} [options]
   * @returns {Promise<any>} JSON contracts are validated by the backend.
   */
  async request(path, options = {}) {
    if (!path.startsWith("/") || path.startsWith("//"))
      throw new Error("Expected API-relative path");
    const headers = new Headers(options.headers);
    headers.set("Content-Type", "application/json");
    headers.set("X-Freight-Request", "1");
    const response = await this.fetchResponse(`/api/v1${path}`, {
      ...options,
      headers,
      credentials: "same-origin",
      redirect: "error",
      signal: options.signal
        ? AbortSignal.any([options.signal, this.lifetime.signal])
        : this.lifetime.signal,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (response.status === 401 && !path.startsWith("/auth/")) this.redirect("/login");
      const detail = Array.isArray(payload.detail)
        ? "Bitte prüfe deine Eingaben. Spielername: 3–24 Zeichen; Passwort: 12–128 Zeichen."
        : payload.detail;
      throw new ApiError(detail || `HTTP ${response.status}`, response.status);
    }
    return payload;
  }

  /** Load one same-origin visual asset without bypassing the API client's lifecycle.
   * @param {string} path
   * @param {RequestInit} [options]
   * @returns {Promise<string>}
   */
  async requestAsset(path, options = {}) {
    if (!path.startsWith("/assets/") || path.startsWith("//"))
      throw new Error("Expected /assets/ path");
    const response = await this.fetchResponse(path, {
      ...options,
      credentials: "same-origin",
      redirect: "error",
      signal: options.signal
        ? AbortSignal.any([options.signal, this.lifetime.signal])
        : this.lifetime.signal,
    });
    if (!response.ok) throw new ApiError(`Asset HTTP ${response.status}`, response.status);
    return response.text();
  }

  /** Load the scoped offer pool for one owned idle vehicle. */
  loadFreightOffers(vehicleId, signal) {
    const query = "?vehicle_id=" + encodeURIComponent(vehicleId);
    return this.request("/contracts" + query, { signal });
  }

  /** Enqueue only the missing stock for one owned idle vehicle. */
  requestFreightRefill(vehicleId, signal) {
    const query = "?vehicle_id=" + encodeURIComponent(vehicleId);
    return this.request("/contracts/refresh" + query, { method: "POST", signal });
  }

  /** Load one offer snapshot. */
  loadFreightOffer(offerId, signal) {
    return this.request("/contracts/" + encodeURIComponent(offerId), { signal });
  }

  /** Quote one offer for the selected vehicle. */
  quoteFreightOffer(offerId, vehicleId, signal) {
    return this.request("/contracts/" + encodeURIComponent(offerId) + "/quote", {
      method: "POST",
      signal,
      body: JSON.stringify({ vehicle_id: vehicleId }),
    });
  }

  /** Dispatch one accepted offer with the selected vehicle. */
  dispatchFreightOffer(offerId, vehicleId, signal) {
    return this.request("/contracts/" + encodeURIComponent(offerId) + "/accept", {
      method: "POST",
      signal,
      body: JSON.stringify({ vehicle_id: vehicleId }),
    });
  }

  /** Purchase one server-priced model. */
  purchaseVehicle(modelId, signal) {
    return this.request("/fleet/purchase", {
      method: "POST",
      signal,
      body: JSON.stringify({ model_id: modelId }),
    });
  }

  /** Abort all in-flight reads and writes; settlement remains server-owned. */
  destroy() {
    this.lifetime.abort();
  }
}
