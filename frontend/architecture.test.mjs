import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { parse } from "espree";

const root = resolve("frontend");
function sourceFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    return entry.isDirectory() ? sourceFiles(path) : path.endsWith(".js") ? [path] : [];
  });
}

/** Inspect resolved modules rather than matching controller filenames. */
function assertBoundaries(name, text) {
  const source = parse(text, { ecmaVersion: "latest", sourceType: "module" });
  function dependencyPath(value) {
    if (!value.startsWith(".")) return value;
    return relative(root, resolve(root, name, "..", value)).replaceAll("\\", "/");
  }
  function checkDependency(value) {
    const dependency = dependencyPath(value);
    assert.ok(!dependency.includes("static/"), name);
    if (name.startsWith("views/") || name.startsWith("ui/"))
      assert.ok(
        !["api.js", "state.js", "bootstrap.js", "application.js"].includes(dependency) &&
          !dependency.startsWith("controllers/") &&
          !dependency.startsWith("map/"),
        name,
      );
    if (name.startsWith("map/"))
      assert.ok(
        !["api.js", "panels.js"].includes(dependency) &&
          !dependency.startsWith("controllers/") &&
          !dependency.startsWith("views/"),
        name,
      );
    if (name === "state.js")
      assert.ok(dependency !== "api.js" && !/^(views|controllers|map)\//.test(dependency), name);
  }
  function visit(node) {
    if (!node || typeof node !== "object") return;
    if (
      ["ImportDeclaration", "ExportNamedDeclaration", "ExportAllDeclaration"].includes(node.type) &&
      node.source
    )
      checkDependency(node.source.value);
    if (node.type === "ImportExpression") {
      if (node.source.type === "Literal") checkDependency(node.source.value);
      if (node.source.type === "TemplateLiteral" && !node.source.expressions.length)
        checkDependency(node.source.quasis[0].value.cooked);
    }
    if (node.type === "CallExpression") {
      const callee = node.callee;
      if (
        (callee.type === "Identifier" && callee.name === "fetch") ||
        (callee.type === "MemberExpression" &&
          (callee.property.name === "fetch" || callee.property.value === "fetch"))
      )
        assert.equal(name, "api.js");
      if (callee.type === "MemberExpression" && callee.property.name === "parseFromString")
        assert.ok(["ui/dom.js", "ui/illustrations.js"].includes(name), name);
    }
    for (const value of Object.values(node)) {
      if (Array.isArray(value)) value.forEach(visit);
      else if (value && typeof value === "object") visit(value);
    }
  }
  visit(source);
}

test("presentation, state and map modules respect import boundaries", () => {
  for (const file of sourceFiles(root))
    assertBoundaries(relative(root, file).replaceAll("\\", "/"), readFileSync(file, "utf8"));
});

test("view boundary rejects controller imports, re-exports and dynamic imports", () => {
  for (const source of [
    'import { GameActions } from "../controllers/game-actions.js";',
    'export * from "../controllers/panel-controller.js";',
    'export { GameState } from "../state.js";',
    'import("../controllers/game-actions.js");',
    "import(`../controllers/game-actions.js`);",
    'globalThis.fetch("/api/v1/fleet");',
    'window["fetch"]("/api/v1/fleet");',
  ])
    assert.throws(() => assertBoundaries("views/fleet.js", source));
  assert.doesNotThrow(() =>
    assertBoundaries("views/fleet.js", 'import { html } from "../ui/dom.js";'),
  );
});

test("the browser entry only imports assets and starts the composition root", () => {
  const source = parse(readFileSync(join(root, "main.js"), "utf8"), {
    ecmaVersion: "latest",
    sourceType: "module",
  });
  assert.equal(
    source.body.filter((statement) => !(statement.type === "ImportDeclaration")).length,
    1,
  );
});
