export const navItems = [
  ["/", "world", "Weltkarte"],
  ["/contracts", "contracts", "Aufträge"],
  ["/fleet", "fleet", "Flotte"],
  ["/fleet?tab=shop", "shop", "Fahrzeugshop"],
  ["/transports", "transports", "Transporte"],
  ["/leaderboard", "leaderboard", "Rangliste"],
];

/** Resolve the visible title of a product URL. @param {URL} url */
export function panelTitle(url) {
  if (url.pathname === "/fleet")
    return url.searchParams.get("tab") === "shop" ? "Fahrzeugshop" : "Deine Flotte";
  return (
    { contracts: "Auftragsbörse", transports: "Unterwegs", leaderboard: "Rangliste" }[
      url.pathname.split("/")[1]
    ] || "Weltkarte"
  );
}

/** Own browser history; notify the application without recreating the map. */
export class BrowserRouter {
  /** @param {Window} browser
   * @param {(url: URL) => void} onNavigate */
  constructor(browser, onNavigate) {
    this.browser = browser;
    this.onNavigate = onNavigate;
    this.onPopState = () => this.navigate(this.browser.location.href, false);
  }
  /** Attach history handling. */
  start() {
    this.browser.addEventListener("popstate", this.onPopState);
  }
  /** Navigate only inside the current origin.
   * @param {string} path
   * @param {boolean} [push]
   */
  navigate(path, push = true) {
    const target = new URL(path, this.browser.location.origin);
    if (target.origin !== this.browser.location.origin) return;
    if (push) this.browser.history.pushState({}, "", target.pathname + target.search);
    this.onNavigate(target);
  }
  /** Release the history listener. */
  destroy() {
    this.browser.removeEventListener("popstate", this.onPopState);
  }
}
