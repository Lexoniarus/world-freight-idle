import js from "@eslint/js";
import globals from "globals";

export default [
  { ignores: ["node_modules/**", "static/dist/**"] },
  js.configs.recommended,
  {
    files: ["frontend/**/*.js", "frontend/**/*.mjs"],
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
    rules: {
      "no-unused-vars": ["error", { argsIgnorePattern: "^_", caughtErrorsIgnorePattern: "^_" }],
      "no-restricted-syntax": [
        "error",
        {
          selector: "MemberExpression[property.name='innerHTML']",
          message: "Use DOM nodes and literal text through ui/dom.js.",
        },
        {
          selector: "MemberExpression[property.name='outerHTML']",
          message: "Use DOM nodes and literal text.",
        },
        {
          selector: "CallExpression[callee.property.name='insertAdjacentHTML']",
          message: "Use DOM nodes and literal text.",
        },
      ],
    },
  },
];
