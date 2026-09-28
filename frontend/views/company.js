import { renderCompanyPreferences } from "../ui/company-preferences.js";
import { dataTable } from "../ui/data-table.js";
import { html } from "../ui/dom.js";
import { metric } from "../ui/components.js";
import { renderChart } from "../ui/charts.js";
import { money, number } from "../format.js";
import { humanLabel } from "../labels.js";

const scopeLabels = {
  company: "Unternehmen",
  city: "Origin-Stadt",
  vehicle: "Fahrzeug",
  transport_class: "Transportklasse",
  distance_band: "Distanzband",
};

/** Private management view; no fetching or domain decisions. */
export function renderCompany(view) {
  const data = view.analytics;
  const scope = view.url.searchParams.get("scope") ?? "company";
  return html`<div class="company-heading">
      <span class="eyebrow">DEIN UNTERNEHMEN</span>
      <h2>${view.user.username}</h2>
      <p>Die Leistung deiner Flotte. Aus belegten Fahrten.</p>
    </div>
    ${renderCompanyPreferences(view)}
    <div class="filter-grid">
      <label class="filter-field"
        ><span>Zeitraum</span
        ><select data-filter="days" aria-label="Zeitraum">
          ${["7", "30", "90", "all"].map((value) => html`<option value="${value}" selected="${value === (view.url.searchParams.get("days") ?? "30")}">${value === "all" ? "Gesamte Historie" : value + " Tage"}</option>`)}
        </select></label
      >
      <label class="filter-field"
        ><span>Auswertung</span
        ><select data-filter="scope" aria-label="Auswertung">
          ${Object.entries(scopeLabels).map(([value, label]) => html`<option value="${value}" selected="${value === scope}" disabled="${value !== "company" && !(view.analyticsChoices?.[value]?.length || scope === value)}">${label}</option>`)}
        </select></label
      >
      ${
        scope !== "company"
          ? html`<label class="filter-field"
              ><span>Auswahl</span
              ><select data-filter="scope_id" aria-label="Scope-Auswahl">
                ${(view.analyticsChoices?.[scope] ?? data?.breakdowns?.[scope] ?? []).map((row) => html`<option value="${row.id}" selected="${row.id === view.url.searchParams.get("scope_id")}">${humanLabel(row.label)}</option>`)}
              </select></label
            >`
          : null
      }
    </div>
    <button class="button quiet" data-action="refresh-analytics">Aktualisieren</button>
    ${
      view.analyticsLoading
        ? html`<p role="status">Statistik wird geladen …</p>`
        : view.analyticsError
          ? html`<p role="alert">Statistik nicht erreichbar.</p>
              <button class="button secondary" data-action="refresh-analytics">
                Erneut versuchen
              </button>`
          : data
            ? renderAnalytics(data)
            : null
    }`;
}

function renderAnalytics(data) {
  const status = data.status;
  const metrics = data.period_totals;
  return html`<h3>Unternehmensstatus · gesamt</h3>
    <div class="metrics company-kpis">
      ${metric("Kapital", money(status.cash))}${metric("Reputation", number(status.reputation))}
      ${metric("Abgeschlossene Transporte", number(status.completed))}${metric("Aktive Transporte", number(status.active_transports))}
      ${metric("Fahrzeuge", number(status.vehicles))}${metric("Einsatzbereit", number(status.idle_vehicles))}${metric("Unterwegs", number(status.enroute_vehicles))}${metric("Aktive Marktstädte", number(status.active_cities))}
    </div>
    <h3>Ausgewählter Zeitraum · ${data.period.timezone}</h3>
    <div class="metrics company-kpis">
      ${metric("Erlöse", money(metrics.revenue_eur))}${metric("Betriebskosten", money(metrics.operating_cost_eur))}${metric("Transportergebnis", money(metrics.profit_eur), "profit")}
      ${metric("Transporte", number(metrics.completed_transports))}${metric("Gefahren", number(metrics.distance_km) + " km")}${metric("Transportiert", number(metrics.tons, 2) + " t")}
    </div>
    <p class="footnote">
      Historie im gewählten Scope: ${number(data.totals.completed_transports)} Transporte ·
      ${money(data.totals.profit_eur)} Ergebnis insgesamt. Ankunftstag in UTC; Fahrzeugkäufe sind
      keine Transportkosten.
    </p>
    ${data.coverage.progress_completed !== data.coverage.recorded_transports ? html`<p class="inline-notice">Dein Fortschritt enthält ${data.coverage.progress_completed} Lieferungen. Für ${data.coverage.recorded_transports} sind historische Finanz- und Leistungsdaten belegt.</p>` : null}
    ${renderChart(
      "Finanzen",
      data.daily,
      [
        ["revenue_eur", "Erlös (€)"],
        ["operating_cost_eur", "Kosten (€)"],
        ["profit_eur", "Ergebnis (€)"],
      ],
      true,
    )}
    ${renderChart("Transportleistung", data.daily, [
      ["completed_transports", "Transporte"],
      ["distance_km", "Kilometer"],
      ["tons", "Tonnen"],
    ])}
    ${Object.entries(data.breakdowns).map(([scope, rows]) => renderBreakdown(scope, rows))}
    <p class="footnote">
      ${data.coverage.unclassified_transports} Transporte ohne V2-Klassifizierung.
      Fahrzeugauswertung nach gespeicherter Fahrzeug-ID; keine historische Modellzuordnung.
    </p>
    <h3>Laufende Fahrten</h3>
    <p>
      ${data.ongoing.length} aktiv · erwartetes Ergebnis
      ${money(data.ongoing.reduce((sum, row) => sum + row.profit_eur, 0))}. Noch nicht im
      historischen Ergebnis enthalten.
    </p>`;
}

function renderBreakdown(scope, rows) {
  const maximum = Math.max(1, ...rows.map((row) => Math.abs(row.profit_eur)));
  return html`<section class="chart">
    <h3>${scopeLabels[scope]}</h3>
    <ul class="performance-bars" aria-label="Ergebnis nach ${scopeLabels[scope]}">
      ${rows.map((row) => html`<li><span>${humanLabel(row.label)}</span><meter min="0" max="${maximum}" value="${Math.abs(row.profit_eur)}" aria-label="Betrag des Ergebnisses für ${humanLabel(row.label)}"></meter><strong class="${row.profit_eur < 0 ? "negative" : "positive"}">${money(row.profit_eur)}</strong></li>`)}
    </ul>
    <div class="table-scroll">
      ${dataTable(
        "Leistung nach " + scopeLabels[scope],
        ["Bereich", "Aufträge", "km", "Ergebnis"],
        rows.map((row) => [
          humanLabel(row.label),
          row.completed_transports,
          number(row.distance_km),
          money(row.profit_eur),
        ]),
      )}
    </div>
    ${rows.length ? null : html`<p class="footnote">Keine belegten Daten für diese Auswahl.</p>`}
  </section>`;
}
