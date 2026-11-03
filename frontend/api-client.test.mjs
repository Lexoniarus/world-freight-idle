import test from "node:test";
import assert from "node:assert/strict";
import { ApiError, GameApiClient } from "./api.js";

test("API client restricts credentials to API v1 and owns request lifetime", async () => {
  const calls = [];
  const api = new GameApiClient(
    async (url, options) => {
      calls.push({ url, options });
      return { ok: true, json: async () => ({ id: "ok" }) };
    },
    () => {},
  );
  assert.deepEqual(
    await api.request("/fleet/purchase", {
      method: "POST",
      body: JSON.stringify({ model_id: "regional" }),
    }),
    { id: "ok" },
  );
  assert.equal(calls[0].url, "/api/v1/fleet/purchase");
  assert.equal(calls[0].options.credentials, "same-origin");
  assert.equal(calls[0].options.redirect, "error");
  assert.equal(calls[0].options.headers.get("X-Freight-Request"), "1");
  await assert.rejects(api.request("https://other.test/"), /API-relative/);
  api.destroy();
  assert.equal(calls[0].options.signal.aborted, true);
});

test("API errors distinguish session, validation and non-JSON failures", async () => {
  const redirects = [];
  let response = {
    ok: false,
    status: 401,
    json: async () => ({ detail: "expired" }),
  };
  const api = new GameApiClient(
    async () => response,
    (path) => redirects.push(path),
  );
  await assert.rejects(
    api.request("/fleet"),
    (error) => error instanceof ApiError && error.status === 401,
  );
  await assert.rejects(api.request("/auth/login"), /expired/);
  assert.deepEqual(redirects, ["/login"]);
  response = {
    ok: false,
    status: 422,
    json: async () => ({ detail: [{ msg: "bad" }] }),
  };
  await assert.rejects(api.request("/auth/register"), /Eingaben/);
  response = {
    ok: false,
    status: 503,
    json: async () => {
      throw new Error("not json");
    },
  };
  await assert.rejects(api.request("/fleet"), /HTTP 503/);
  api.destroy();
});

test("asset requests stay same-origin and outside the JSON API prefix", async () => {
  let requested = "";
  const api = new GameApiClient(async (url) => {
    requested = String(url);
    return new Response("<svg/>", { status: 200 });
  });

  assert.equal(await api.requestAsset("/assets/test.svg"), "<svg/>");
  assert.equal(requested, "/assets/test.svg");
  await assert.rejects(api.requestAsset("/other/test.svg"), /Expected \/assets\//);
  api.destroy();
});
