/** Own every mutation of the shared panel presentation model. */
export class PanelViewState {
  /** @param {import('../types.js').PanelView} value */
  constructor(value) {
    this.value = value;
  }
  /** Report whether a mutation or quote currently owns the panel.
   * @returns {boolean}
   */
  isBusy() {
    return this.value.busy;
  }
  /** Return the currently published quote.
   * @returns {import('../types.js').Quote | null}
   */
  currentQuote() {
    return this.value.quote;
  }
  /** Publish quote progress.
   * @param {boolean} active
   * @returns {void}
   */
  setQuotePending(active) {
    this.value.quoting = active;
  }
  /** Select a vehicle and discard prior economics.
   * @param {string} vehicleId
   * @returns {void}
   */
  selectVehicle(vehicleId) {
    this.value.selectedVehicle = vehicleId;
    this.value.url.searchParams.set("vehicle", vehicleId);
    window.history.replaceState({}, "", this.value.url.pathname + this.value.url.search);
    this.value.quote = null;
  }
  /** Publish a quote belonging to the current selection.
   * @param {import('../types.js').Quote | null} quote
   * @returns {void}
   */
  publishQuote(quote) {
    this.value.quote = quote;
  }
  /** Publish mutation progress.
   * @param {boolean} active
   * @returns {void}
   */
  setMutationPending(active) {
    this.value.mutating = active;
  }
  /** Publish one synchronized game and market-detail snapshot.
   * @param {import('../types.js').GameSnapshot} state
   * @param {import('../types.js').Contract | null} detailContract
   * @param {string | null} detailId
   * @param {boolean} marketLoaded
   * @param {boolean} marketStale
   * @returns {void}
   */
  publishGameState(state, detailContract, detailId, marketLoaded, marketStale) {
    Object.assign(this.value, {
      state,
      detailContract,
      detailId,
      marketLoaded,
      marketStale,
    });
  }
  /** Publish route-local city labels.
   * @param {string} cityUid
   * @param {Array<import('../types.js').FacilityLocation>} cities
   * @param {Array<string>} activeCities
   * @returns {void}
   */
  publishCityContext(cityUid, cities, activeCities) {
    Object.assign(this.value, {
      cityUid,
      cities,
      activeCities,
      marketCities: cities.filter((city) => activeCities.includes(city.city_uid)),
    });
  }
  /** Mark a preference read as pending.
   * @returns {void}
   */
  beginPreferenceLoad() {
    this.value.preferenceStatus = "loading";
  }
  /** Publish the curated preference palette and confirmed color.
   * @param {Array<string>} palette
   * @param {string} color
   * @returns {void}
   */
  publishPreferences(palette, color) {
    this.value.preferenceStatus = "ready";
    this.value.companyPalette = palette;
    this.value.user.company_color = color;
  }
  /** Mark a preference read as unavailable.
   * @returns {void}
   */
  failPreferenceLoad() {
    this.value.preferenceStatus = "error";
  }
  /** Publish whether the latest preference write failed.
   * @param {boolean} failed
   * @returns {void}
   */
  setPreferenceSaveError(failed) {
    this.value.preferenceSaveError = failed;
  }
  /** Publish one optimistic or confirmed company color.
   * @param {string} color
   * @returns {void}
   */
  publishCompanyColor(color) {
    this.value.user.company_color = color;
  }
  /** Report whether a color belongs to the server-provided palette.
   * @param {string} color
   * @returns {boolean}
   */
  acceptsCompanyColor(color) {
    return Boolean(this.value.companyPalette?.includes(color));
  }
  /** Mark analytics loading and clear an obsolete error.
   * @returns {void}
   */
  beginAnalyticsLoad() {
    this.value.analyticsLoading = true;
    this.value.analyticsError = false;
  }
  /** Publish one analytics response and its company breakdowns.
   * @param {import('../types.js').AnalyticsReport & {scope: {type: string}}} result
   * @returns {void}
   */
  publishAnalytics(result) {
    this.value.analytics = result;
    if (result.scope.type === "company") this.value.analyticsChoices = result.breakdowns;
  }
  /** Mark the latest analytics read as failed.
   * @returns {void}
   */
  failAnalyticsLoad() {
    this.value.analyticsError = true;
  }
  /** Finish the current analytics request.
   * @returns {void}
   */
  finishAnalyticsLoad() {
    this.value.analyticsLoading = false;
  }
  /** Reset selection state for one navigation route.
   * @param {URL} url
   * @returns {void}
   */
  selectRoute(url) {
    Object.assign(this.value, {
      url,
      quote: null,
      selectedVehicle: url.searchParams.get("vehicle") ?? "",
      rankings: null,
      panelError: false,
    });
  }
  /** Publish one auxiliary panel response.
   * @param {string} endpoint
   * @param {any} result
   * @returns {void}
   */
  publishDetails(endpoint, result) {
    if (endpoint === "/leaderboard") this.value.rankings = result.players;
    else this.value.catalogue = result;
    this.value.panelError = false;
  }
  /** Mark an auxiliary panel response as failed.
   * @returns {void}
   */
  failDetails() {
    this.value.panelError = true;
  }
  /** Replace an invalid vehicle selection and clear its quote.
   * @param {string} selectedVehicle
   * @returns {void}
   */
  replaceVehicleSelection(selectedVehicle) {
    this.value.selectedVehicle = selectedVehicle;
    this.value.quote = null;
  }
}
