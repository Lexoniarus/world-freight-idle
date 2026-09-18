import { html } from "../ui/dom.js";
import { icon } from "../ui/illustrations.js";
import { number } from "../format.js";

/** Render the public ranking with literal player names.
 * @param {import('../types.js').PanelView} view
 * @returns {DocumentFragment}
 */
export function renderRanking({ rankings, user }) {
  return html`<div class="ranking-hero">
      ${icon("leaderboard", 48)}
      <h2>Lieferung für Lieferung<br />nach oben.</h2>
      <p>Die erfolgreichsten Spediteure – gemessen an abgeschlossenen Transporten.</p>
    </div>
    ${
      rankings
        ? html`<ol class="rankings">
            ${rankings.map((player, index) => renderRank(player, index + 1, player.username === user.username))}
          </ol>`
        : html`<p class="loading">Rangliste wird geladen …</p>`
    }`;
}

/** Render one competitor's public delivery count. */
function renderRank(player, rank, ownCompany) {
  return html`<li class="${ownCompany ? "you" : ""}">
    <span class="rank">${String(rank).padStart(2, "0")}</span>
    <div>
      <strong>${player.username}</strong>${ownCompany ? html`<small>Deine Spedition</small>` : null}
    </div>
    <b>${number(player.completed)}<small>Lieferungen</small></b>
  </li>`;
}
