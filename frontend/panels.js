import { html } from "./ui/dom.js";
import { emptyState } from "./ui/components.js";
import { renderContracts } from "./views/contracts.js";
import { renderFleet } from "./views/fleet.js";
import { renderShop } from "./views/shop.js";
import { renderTransports } from "./views/transports.js";
import { renderRanking } from "./views/ranking.js";

/** Select a presentation module for a product URL.
 * @param {import('./types.js').PanelView} view
 * @returns {DocumentFragment}
 */
export function renderPanel(view) {
  if (view.panelError)
    return html`<p class="inline-notice">Diese Daten konnten nicht geladen werden.</p>
      <button class="button secondary" data-action="retry-panel">Erneut versuchen</button>`;
  if (!view.state)
    return html`<div class="loading"><span class="spinner"></span> Spielstand wird geladen …</div>`;
  const section = view.url.pathname.split("/")[1];
  const views = {
    contracts: renderContracts,
    fleet: view.url.searchParams.get("tab") === "shop" ? renderShop : renderFleet,
    transports: renderTransports,
    leaderboard: renderRanking,
  };
  return (
    views[section]?.(view) ??
    emptyState("Ansicht nicht gefunden", "Wähle einen Bereich in der Navigation.")
  );
}
