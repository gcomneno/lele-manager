## v1.11.0 — Commercial-grade local-first product experience

LeLe Manager v1.11.0 completes the first commercial-grade product-experience
tranche without changing the local-first architecture or the authority of the
Markdown vault.

### Product experience

- coherent product shell and grouped navigation;
- Dashboard as the default `/app/` destination;
- explicit first-run, empty, partial and ready workspace states;
- Settings with effective local runtime paths and semantic storage roles;
- explicit bounded support diagnostics with preview-before-export;
- About with authoritative version, GiadaWare attribution, MIT license,
  local-first statement and support links;
- direct Giada UI adoption in shipped GUI code;
- English/Italian GUI localization with persistent explicit selection;
- keyboard, focus, responsive and deterministic Playwright coverage.

### Local-first guarantees

The Markdown vault remains authoritative for approved lessons. Projection data
and topic models remain derived or rebuildable. TritaLeLe candidates still
require explicit approval before publication.

LeLe Manager introduces no account, telemetry, cloud storage or remote
knowledge service.

### Native packages

Linux, macOS and Windows native archives remain the normal non-technical
installation path. They are self-contained and do not require Python, Node.js,
npm, a virtual environment or a repository checkout.

The release workflow now road-tests the actual published-style native archive
before upload. It extracts the archive, launches the packaged executable on
loopback with isolated data/cache/vault directories and verifies:

- `/health`;
- `/runtime/info`;
- packaged `/app/`;
- packaged `/app/LICENSE`;
- `/about`;
- `/settings/runtime`;
- version coherence;
- runtime-path isolation outside the extracted release package.

Native builds also reject stale installed package metadata before PyInstaller
can create a version-incoherent executable.

### Verification performed for issue #152

- 601 Python tests passed;
- Ruff passed;
- mypy passed for 59 source files;
- Svelte/TypeScript checks: 0 errors, 0 warnings;
- full npm audit: 0 vulnerabilities;
- runtime-only npm audit: 0 vulnerabilities;
- Playwright: 68 passed, 1 intentional screenshot skip;
- Python sdist and wheel metadata checks passed;
- installed-wheel smoke passed;
- Linux x86_64 published-style native archive successfully built, extracted,
  launched and verified.

### Upgrade compatibility

No intentional breaking changes are introduced in the public API or CLI.
Persistent user data remains outside native installation directories, so
replacing the extracted application package does not require moving the vault
or persistent application state.

---

## v1.1.1 — Documentation hardening

This is a small patch release focused on repo/product hygiene.

### Added
- `CHANGELOG.md` (Keep a Changelog format + compare links)

### Why it matters
A recruiter (or reviewer) can quickly understand project maturity and change history.

### Quick start
```bash
pip install -e .
lele --help
```


## v1.2.0 — Text-based Similarity + CLI Suggest

This release introduces free-text similarity and a unified CLI client.

### Added

- `POST /similar` endpoint:
  - compute similarity starting from arbitrary text (no `lesson_id` required)
  - same response schema as `/lessons/{id}/similar`
  - returns 503 if model is missing
  - returns 400 if text is empty

- `lele suggest` CLI command:
  - `--text "..."`
  - `--file note.md`
  - `cat note.md | lele suggest`
  - `--watch note.md --every 2`
  - supports `--top-k` and `--min-score`
  - optional `--json` output

### Why it matters

You can now get similarity suggestions *while writing*, without first creating a lesson entry.

This is the first step toward real-time LeLe assistance inside your workflow.

### Quick smoke test

```bash
./scripts/lele-api-dev.sh
lele suggest --text "pytest src layout conftest PYTHONPATH"
```
