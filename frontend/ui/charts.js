import { dataTable } from "./data-table.js";
import { html } from "./dom.js";
import { number } from "../format.js";

/** Scale independent series for comparison; absolute values remain in the table. */
export function chartPoints(rows, key, domain = null) {
  const values = rows.map((row) => row[key]);
  const low = domain?.[0] ?? Math.min(0, ...values);
  const high = domain?.[1] ?? Math.max(1, ...values);
  return values
    .map(
      (value, index) =>
        `${20 + (index / Math.max(1, values.length - 1)) * 560},${150 - ((value - low) / (high - low)) * 130}`,
    )
    .join(" ");
}

/** SVG series plus a complete keyboard-accessible table, never color alone. */
export function renderChart(title, rows, series, sharedScale = false) {
  const values = rows.flatMap((row) => series.map(([key]) => row[key]));
  const domain = sharedScale ? [Math.min(0, ...values), Math.max(1, ...values)] : null;
  const scaleLabel = sharedScale ? "Gemeinsame Skala in Euro" : "Je Reihe relative Skala";
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 600 170");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", title + ". " + scaleLabel + "; genaue Werte in der Tabelle.");
  series.forEach(([key, label], index) => {
    const line = document.createElementNS(svg.namespaceURI, "polyline");
    line.setAttribute("points", chartPoints(rows, key, domain));
    line.setAttribute("class", "chart-line chart-series-" + index);
    line.setAttribute("aria-label", label);
    svg.append(line);
    if (rows.length === 1) {
      const point = document.createElementNS(svg.namespaceURI, "circle");
      const [x, y] = chartPoints(rows, key, domain).split(",");
      point.setAttribute("cx", x);
      point.setAttribute("cy", y);
      point.setAttribute("r", String(4 + index * 2));
      point.setAttribute("class", "chart-line chart-series-" + index);
      svg.append(point);
    }
  });
  return html`<section class="chart">
    <h3>${title}</h3>
    <div class="chart-legend">
      ${series.map(([, label], index) => html`<span class="chart-series-${index}">${["━", "┄", "·"][index]} ${label}</span>`)}
    </div>
    ${rows.length ? svg : html`<p class="empty-state">Noch keine belegten Transporte in dieser Auswahl.</p>`}
    <p class="footnote">
      ${scaleLabel} · UTC · ${rows[0]?.date ?? ""} – ${rows.at(-1)?.date ?? ""}
    </p>
    <details data-disclosure="${title}">
      <summary>Werte als Tabelle</summary>
      <div class="table-scroll">
        ${dataTable(
          title + " · UTC",
          ["Tag", ...series.map(([, label]) => label)],
          rows.map((row) => [row.date, ...series.map(([key]) => number(row[key], 2))]),
        )}
      </div>
    </details>
  </section>`;
}
