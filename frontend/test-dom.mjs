import { JSDOM } from "jsdom";

const dom = new JSDOM("<!doctype html><html><body><div id='app'></div></body></html>", {
  url: "http://test/",
});
for (const name of [
  "window",
  "document",
  "DOMParser",
  "Node",
  "NodeFilter",
  "Element",
  "HTMLElement",
  "HTMLSelectElement",
  "HTMLInputElement",
  "HTMLImageElement",
  "CustomEvent",
  "Event",
  "EventTarget",
  "AbortController",
  "AbortSignal",
  "FormData",
  "location",
]) {
  globalThis[name] = dom.window[name];
}
export const browser = dom.window;
