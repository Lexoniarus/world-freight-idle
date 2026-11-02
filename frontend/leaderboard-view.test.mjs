import "./test-dom.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { renderPanel } from "./panels.js";

test("leaderboard renders untrusted ranking names as text", () => {
  const ranking = renderPanel({
    url: new URL("http://test/leaderboard"),
    state: { transports: [] },
    rankings: [{ username: "<script>x</script>", completed: 2 }],
    user: { username: "x" },
  });

  assert.ok(ranking.textContent.includes("<script>x</script>"));
  assert.equal(ranking.querySelector("script"), null);
});
