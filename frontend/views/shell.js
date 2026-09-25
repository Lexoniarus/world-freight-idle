import { layerLabels } from "../layer-presets.js";
import { html } from "../ui/dom.js";
import { icon } from "../ui/illustrations.js";
import { routeLink } from "../ui/components.js";
import { navItems } from "../navigation.js";

/** Render the persistent map shell and navigation.
 * @param {{username: string}} user
 * @returns {DocumentFragment}
 */
export function renderShell(user) {
  return html` <a class="skip-link" href="#navigation">Zur Spielnavigation</a>
    <main id="game" aria-label="Deine Logistikwelt">
      <div id="world-map" role="region" aria-label="Interaktive Weltkarte" aria-busy="true"></div>
      <header class="hud">
        <a href="/" data-nav class="brand"
          >${icon("world", 31)}<span
            >WORLD<span class="brand-light">FREIGHT</span><small>DEINE LOGISTIKWELT</small></span
          ></a
        >
        <div class="hud-divider"></div>
        <div class="hud-stat cash-stat">
          <span>VERFÜGBARES KAPITAL</span><strong id="cash">—</strong>
        </div>
        <div class="hud-stat"><span>REPUTATION</span><strong id="reputation">—</strong></div>
        <div class="hud-stat fleet-stat">
          <span>FLOTTE</span><strong id="fleet-count">—</strong
          ><small id="fleet-state">Status wird geladen</small>
        </div>
        <button class="city-context-button" data-action="focus-city">
          <span>AKTUELLE STADT</span><strong id="current-city-label">Alle Städte</strong>
        </button>
        <div class="player-chip">
          <span class="avatar">${user.username.slice(0, 2).toUpperCase()}</span
          ><span><strong>${user.username}</strong><small id="connection">Verbinde …</small></span>
        </div>
      </header>
      <nav id="navigation" class="nav-rail" aria-label="Spielnavigation">
        ${navItems.map(([path, name, label]) =>
          routeLink(path, [icon(name), html`<span>${label}</span>`], "nav-item"),
        )}
        <button
          class="nav-item more-navigation"
          data-action="more-navigation"
          aria-expanded="false"
        >
          ${icon("layers")}<span>Mehr</span>
        </button>
        <button class="nav-item logout" data-action="logout" aria-label="Abmelden">
          ${icon("logout")}<span>Abmelden</span>
        </button>
      </nav>
      <div id="welcome" class="mission-card" hidden>
        <h2>Dein erster Auftrag wartet.</h2>
        ${routeLink("/contracts", ["Auftrag auswählen ", icon("arrow", 17)], "button primary")}
      </div>
      <section id="panel" class="context-panel" aria-labelledby="panel-title" hidden>
        <button id="sheet-handle" class="sheet-handle" aria-label="Panelhöhe ändern">
          <span></span>
        </button>
        <header class="panel-heading">
          <div>
            <span class="eyebrow">DISPOSITION / WORLD FREIGHT</span>
            <h1 id="panel-title" tabindex="-1"></h1>
          </div>
          <button
            class="icon-button"
            data-action="panel-mode"
            aria-label="Managementansicht umschalten"
          >
            ${icon("layers")}
          </button>
          <button class="icon-button" data-action="close" aria-label="Panel schließen">
            ${icon("close")}
          </button>
        </header>
        <div id="panel-content" class="panel-content"></div>
      </section>
      <div class="map-tools">
        <button class="map-tool" data-action="focus-city" aria-label="Aktuelle Stadt">
          ${icon("pin")}<span>Aktuelle Stadt</span>
        </button>
        <button class="map-tool" data-action="focus-fleet" aria-label="Flotte zentrieren">
          ${icon("target")}<span>Meine Flotte</span>
        </button>
        <details class="layer-menu">
          <summary aria-label="Kartenlayer">${icon("layers")}<span>Layer</span></summary>
          <div>
            <h3>Kartenlayer</h3>
            ${Object.entries(layerLabels).map(
              ([name, label]) =>
                html`<label><input type="checkbox" data-layer="${name}" checked />${label}</label>`,
            )}
            <label><input type="checkbox" id="object-grouping" checked />Objekte gruppieren</label>
            <button class="button quiet" data-action="reset-layers">Ansicht zurücksetzen</button>
          </div>
        </details>
      </div>
      <div id="map-notice" class="map-notice" role="status" hidden></div>
      <div id="sync-notice" class="sync-notice" role="status" hidden></div>
      <div id="toasts" class="toasts" role="status" aria-live="polite"></div>
    </main>`;
}
