import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { parse } from "espree";
import { GameApplication } from "./application.js";
import { releaseAll, reportCleanup } from "./lifecycle.js";

function worldMapClass() {
  const source = readFileSync(new URL("./map/world-map.js", import.meta.url), "utf8");
  const ast = parse(source, { ecmaVersion: "latest", sourceType: "module", range: true });
  const declaration = ast.body.find((node) => node.type === "ExportNamedDeclaration").declaration;
  return new Function("releaseAll", "return " + source.slice(...declaration.range))(releaseAll);
}

test("cleanup attempts every resource and aggregates original failures", () => {
  const calls = [];
  const first = new Error("first"),
    second = new Error("second");
  assert.throws(
    () =>
      releaseAll([
        () => {
          calls.push(1);
          throw first;
        },
        () => {
          calls.push(2);
        },
        () => {
          calls.push(3);
          throw second;
        },
        () => {
          calls.push(4);
        },
      ]),
    (error) =>
      error instanceof AggregateError && error.errors[0] === first && error.errors[1] === second,
  );
  assert.deepEqual(calls, [1, 2, 3, 4]);
  releaseAll([]);
});

test("application cleanup remains complete and idempotent after a failure", () => {
  const calls = [];
  const app = new GameApplication({
    scheduler: {
      destroy() {
        calls.push("scheduler");
        throw new Error("timer");
      },
    },
    map: {
      destroy() {
        calls.push("map");
        throw new Error("map");
      },
    },
    api: {
      destroy() {
        calls.push("api");
      },
    },
  });
  assert.throws(() => app.destroy(), AggregateError);
  assert.equal(app.disposed, true);
  app.destroy();
  assert.deepEqual(calls, ["scheduler", "map", "api"]);
});

test("world map cleanup reaches native map removal after component errors", () => {
  const WorldMap = worldMapClass();
  const calls = [];
  const map = Object.create(WorldMap.prototype);
  for (const name of ["animator", "groups", "opportunities", "vehicleIcons"]) {
    map[name] = {
      destroy() {
        calls.push(name);
        if (name === "groups") throw new Error(name);
      },
    };
  }
  map.hoverPopup = {
    remove() {
      calls.push("popup");
      throw new Error("popup");
    },
  };
  map.map = {
    remove() {
      calls.push("native-map");
    },
  };
  assert.throws(() => map.destroy(), AggregateError);
  map.destroy();
  assert.deepEqual(calls, [
    "animator",
    "groups",
    "opportunities",
    "popup",
    "vehicleIcons",
    "native-map",
  ]);
});

test("logout and cleanup reporting preserve workflow results", async () => {
  const reported = [];
  const original = console.error;
  console.error = (...args) => reported.push(args);
  try {
    const redirects = [];
    const app = new GameApplication({
      api: {
        request: async () => {},
        destroy() {
          throw new Error("close");
        },
      },
      redirect: (path) => redirects.push(path),
    });
    await app.logout();
    assert.deepEqual(redirects, ["/login"]);
    assert.equal(reported.length, 1);
    assert.ok(reported[0][1] instanceof AggregateError);
    reportCleanup([() => {}]);
  } finally {
    console.error = original;
  }
});

test("public application, map and controller methods declare module contracts", () => {
  const files = [
    "application.js",
    "map/world-map.js",
    ...readdirSync(new URL("./controllers", import.meta.url)).map((name) => "controllers/" + name),
  ];
  for (const file of files) {
    const source = readFileSync(new URL(file, import.meta.url), "utf8");
    const ast = parse(source, {
      ecmaVersion: "latest",
      sourceType: "module",
      comment: true,
      range: true,
    });
    for (const node of ast.body) {
      const klass = node.declaration;
      if (klass?.type !== "ClassDeclaration") continue;
      for (const method of klass.body.body) {
        const comment = ast.comments.filter((item) => item.range[1] <= method.range[0]).at(-1);
        assert.ok(
          comment && !source.slice(comment.range[1], method.range[0]).trim(),
          file + ":" + method.key.name,
        );
        const tags = comment.value.match(/@param /g) ?? [];
        assert.ok(
          tags.length >= method.value.params.length,
          file + ":" + method.key.name + " parameter contracts",
        );
        if (method.kind !== "constructor") assert.match(comment.value, /@returns /);
      }
    }
  }
});
