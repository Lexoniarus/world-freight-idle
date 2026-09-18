import { html } from "../ui/dom.js";
import { icon, truckIllustration } from "../ui/illustrations.js";

/** Render the authentication surface without network or event handling. */
export function renderAuth() {
  return html`<main class="auth-layout">
    <section class="auth-world">
      <a href="/login" class="brand"
        >${icon("world", 32)}<span
          >WORLD<span class="brand-light">FREIGHT</span><small>BUILD YOUR NETWORK</small></span
        ></a
      >
      <div class="auth-pitch">
        <div class="eyebrow">DEINE WELT. DEINE WEGE.</div>
        <h1>Ein Truck.<br />Tausend<br /><em>Möglichkeiten.</em></h1>
        <p>Verbinde Städte. Bewege Güter.<br />Baue eine Flotte, die niemals stillsteht.</p>
      </div>
      <div class="auth-road">
        <span class="road-city city-one">BERLIN</span
        ><span class="road-city city-two">HAMBURG</span>${truckIllustration()}
      </div>
      <div class="auth-caption">
        <span>01 / EUROPEAN ROAD FREIGHT</span><span>DEIN NETZWERK BEGINNT HIER</span>
      </div>
    </section>
    <section class="auth-panel">
      <div class="auth-form-wrap">
        <div class="eyebrow">DEINE SPEDITION WARTET</div>
        <h2 id="form-title">Willkommen zurück.</h2>
        <p id="form-help">Melde dich an und bring deine Flotte auf Kurs.</p>
        <div class="tabs auth-tabs">
          <button id="login-tab" class="active" aria-pressed="true">Anmelden</button
          ><button id="register-tab" aria-pressed="false">Konto erstellen</button>
        </div>
        <form id="auth-form">
          <label for="username">Spielername</label
          ><input
            id="username"
            name="username"
            autocomplete="username"
            placeholder="Dein Spielername"
            minlength="3"
            maxlength="24"
            required
          />
          <label for="password">Passwort</label
          ><input
            id="password"
            name="password"
            type="password"
            autocomplete="current-password"
            minlength="12"
            maxlength="128"
            placeholder="Mindestens 12 Zeichen"
            required
          />
          <p class="form-hint">Spielername: 3–24 Zeichen · Passwort: 12–128 Zeichen</p>
          <p id="auth-status" class="form-error" role="alert"></p>
          <button id="submit-auth" class="button primary" type="submit">
            Anmelden ${icon("arrow", 18)}
          </button>
        </form>
        <div class="starter-note">
          ${icon("fleet", 26)}
          <p>
            <strong>Große Pläne fangen klein an.</strong><br />Starte mit einem Lkw und 25.000 €
            Kapital.
          </p>
        </div>
        <p class="auth-footer">World Freight Idle <span>·</span> Deine Logistikwelt</p>
      </div>
    </section>
  </main>`;
}
