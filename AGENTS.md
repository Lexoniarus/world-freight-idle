# Repository engineering rules

- Python follows PEP 8 and uses explicit, descriptive names.
- Prefer OOP at stateful boundaries and dependency injection for external systems.
- A function or method performs one coherent task; orchestration belongs in higher-level services.
- No concrete Python-Core callable may be added without an explicit counter-test in `tests/function_test_manifest.py`.
- Keep the Python-Core at 100 % statement coverage for this MVP unless a deliberate documented exception is approved.
- External provider calls must be cached where appropriate, logged, traceable and fail explicitly; never silently invent routing data.
- Add or update product, target, milestone and technical documentation when scope changes.
- Structured logging and trace propagation are mandatory for externally visible workflows.

- Frontend uses native ES modules, camelCase functions and kebab-case filenames.
- Stateful UI components own and dispose their timers, listeners and requests.
- Views never fetch; game HTTP goes through frontend/api.js. Map tiles are separate.
- Render untrusted values as text/DOM attributes, never HTML strings.
- Run ESLint, Stylelint, Prettier, checkJs and behavior/architecture tests via the shared quality gate.
- Passing tools do not replace a review of each function's responsibility.

## Mandatory Git workflow

- Follow docs/BRANCHING.md. Work on one named feature/fix/refactor/docs/chore/test/hotfix branch per task, based on current main.
- Never commit directly to main after the initial repository bootstrap; no force-push on shared branches.
- Enable repository hooks with `git config --local core.hooksPath .githooks` after cloning; do not bypass them with --no-verify.
- Review the staged diff and exclude player databases, backups, secrets and generated assets. Only the documented vehicle reference catalogue is versioned.
- Integration requires the quality gate, browser regression and an explicit architecture/documentation review. A local-only repository uses fast-forward integration; a remote uses reviewed squash PRs.
- Do not create remotes, publish branches or release tags without user authorization. Do not claim server-side protection before it is configured.
