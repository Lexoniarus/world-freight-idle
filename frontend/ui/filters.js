import { html } from "./dom.js";

/** Reusable URL-backed filter; controllers own changes. */
export function selectFilter(name, label, options, value = "", all = "Alle") {
  return html`<label class="filter-field"
    ><span>${label}</span
    ><select data-filter="${name}" aria-label="${label}">
      <option value="" selected="${!value}">${all}</option>
      ${options.map(([id, text]) => html`<option value="${id}" selected="${value === id}">${text}</option>`)}
    </select></label
  >`;
}
export function cityFilter(view) {
  return selectFilter(
    "city",
    "Stadt",
    (view.cities ?? []).map((item) => [item.city_uid, item.city]),
    view.cityUid ?? "",
    "Alle Städte",
  );
}
export function searchFilter(name, label, url) {
  return html`<label class="filter-field"
    ><span>${label}</span
    ><input
      type="search"
      data-filter="${name}"
      aria-label="${label}"
      value="${url.searchParams.get(name) ?? ""}"
      placeholder="Suchen …"
  /></label>`;
}
