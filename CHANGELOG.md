# Changelog

All notable changes to **LeLe Manager** will be documented in this file.

This project follows **Semantic Versioning** (`MAJOR.MINOR.PATCH`):
- **MAJOR**: breaking changes (API / formats)
- **MINOR**: backward-compatible features
- **PATCH**: bugfix / internal improvements

The format is based on **Keep a Changelog**.

## [Unreleased]

## [1.11.1] - 2026-08-09

### Fixed
- Native launcher shutdown now treats `Ctrl+C` as an intentional clean exit
  after Uvicorn completes its shutdown, preventing the packaged PyInstaller
  application from printing an unhandled `KeyboardInterrupt` traceback.

### Compatibility
- No intentional breaking changes are introduced in the public API, CLI,
  Markdown vault authority, persistent local data or native package layout.

## [1.11.0] - 2026-08-08

### Added
- **Commercial-grade product experience for v1.11.0:** coherent product shell
  and navigation hierarchy, Dashboard and explicit first-run states, read-only
  Settings/runtime transparency, bounded support diagnostics, and an About
  surface with product identity, MIT license, GiadaWare attribution and
  local-first support links.
- Direct Giada UI consumption across the shipped GUI through the pinned
  immutable-artifact model, with English/Italian localization and persistent
  explicit locale selection.
- Published-style native release smoke for Linux, macOS and Windows release
  jobs. CI now extracts the actual release archive, launches the packaged
  executable, and checks loopback health, runtime version, packaged GUI,
  license, About and Settings/runtime before artifact upload.

### Changed
- `/app/` now opens on the Dashboard while Browse and existing domain workflows
  remain directly reachable.
- Native builds fail before PyInstaller packaging when installed
  `lele-manager` metadata does not match the source project version, preventing
  stale-version executables from being published.
- Native release verification uses isolated data, cache and vault directories
  and rejects runtime paths outside that temporary road-test environment.
- README and maintained GUI guides now document native packages as the normal
  non-technical installation path while preserving source-checkout development
  instructions.

### Compatibility
- No intentional breaking changes are introduced in the public API, CLI,
  Markdown vault authority, TritaLeLe approval boundary or local-first storage
  model.
- No account, telemetry, cloud storage or remote knowledge dependency is
  introduced.
- Persistent user data remains outside native installation directories.

### Verification
- Full Python suite: 601 tests passed.
- Frontend type/Svelte checks completed with zero errors and warnings.
- Full and runtime-only npm audits report zero vulnerabilities.
- Playwright: 68 passed, 1 intentional documentation-screenshot skip.
- Python sdist/wheel build, metadata check and installed-wheel smoke passed.
- Linux published-style native archive was extracted, launched and verified
  successfully with runtime data isolated outside the release package.

## [1.10.1] - 2026-08-08

### Added
- **LeLe Manager PKPS consumer boundary:** local PKPS v1 GYTE lesson-package
  import through the existing TritaLeLe staging boundary, with strict
  validation for directories and single-root ZIP packages, immutable
  provenance, idempotency by package ID/content hash, and no vault or derived
  artifact writes before explicit approval.
- **Native desktop packaging:** self-contained packages for Linux, macOS, and
  Windows, with a local FastAPI launcher, health-endpoint readiness wait, and
  automatic browser opening of the GUI.
- Platform-specific `LEGGIMI_PRIMA.txt` guides for Linux, macOS, and Windows.

### Changed
- Introduced and consolidated the **LeLe Manager brand design system**.
- Extended **Giada UI** foundation adoption across the GUI.
- Completed GUI localization.
- Added subtle, non-intrusive motion to the LeLe mascot.
- GUI and native builds now use cross-platform Python entrypoints.
- The Release workflow now builds native artifacts on Linux, macOS, and
  Windows and requires explicit opt-in for manual PyPI publishing.
- CI, release, and security workflows now use GitHub Actions versions
  compatible with Node.js 24.

### Compatibility
- No intentional breaking changes were introduced in the public API or CLI.
- Persistent data remains outside the native installation directory so
  upgrades do not require moving the vault.

## [1.10.0] - 2026-08-04

### Added
- **TritaLeLe:** flusso controllato per acquisire fonti Markdown, testo,
  standard input e contenuti in memoria, con normalizzazione deterministica,
  fingerprint SHA-256, chunking, staging, review, rifiuto e approvazione
  esplicita dei candidati.
- CLI, API e GUI complete per anteprima, ingestione, revisione e approvazione
  TritaLeLe.
- **Projection store:** contratto backend-neutral, adapter JSONL atomico,
  adapter per il vault Markdown canonico e facade di compatibilità con i
  consumer legacy.
- **Vault Doctor:** diagnostica read-only disponibile tramite CLI, API e
  pannello Ops.
- Rilevamento e revisione read-only di duplicati esatti e near-duplicate,
  inclusa una vista GUI dedicata.
- Piano di importazione tipizzato e anteprima `--dry-run` deterministica.
- Feed API versionato per l'esposizione di lesson verso consumer esterni.

### Changed
- API, import, vault e componenti ML passano attraverso il composition
  boundary e il projection-store contract, mantenendo la compatibilità con
  la proiezione JSONL esistente.
- La GUI locale include i workflow TritaLeLe, Duplicates e Vault Doctor e
  dispone di copertura Playwright isolata.
- Il processo di release compila il frontend e incorpora la GUI sia nella
  wheel sia nella sdist.
- CI e release usano lo stesso entrypoint di build e verificano installazione,
  CLI, API e GUI dalla wheel diretta e dalla wheel ricostruita dalla sdist.
- La documentazione inglese è canonica e dispone di mirror italiani
  mantenuti.

### Fixed
- L'import non riscrive frontmatter già valido.
- L'anteprima dry-run usa i candidati effettivamente risolti e traduce
  correttamente gli errori di input.
- Gli artefatti Python di release includono ora la GUI Svelte compilata.

### Security
- Aggiornati DOMPurify a 3.4.13, PostCSS a 8.5.25 e Nanoid a 3.3.17.
- `npm audit` completo e `npm audit --omit=dev` non riportano vulnerabilità.

### Documentation
- Aggiunti guida utente GUI, ADR sul projection store e ADR sulla strategia
  di packaging locale FastAPI/Svelte.
- Aggiunti screenshot GUI deterministici e relativo workflow Playwright.
- Aggiornati README, roadmap, guida contributori e policy documentale in
  inglese e italiano.

### Compatibility
- Non sono introdotte incompatibilità intenzionali nelle API o nella CLI
  pubblica.
- `LELE_DATA_PATH` e `LELE_MODEL_PATH` restano temporaneamente supportate;
  per nuove configurazioni usare `LELE_DATA_DIR` e `LELE_CACHE_DIR`.

## [1.9.0] - 2026-07-05

### Added
- **Explain similarity (Fase 4.1, #90):** `explain=true` su `/similar`, `/editor/suggest`, `GET /lessons/{id}/similar` con rank, topic, `tags_shared` e meta query.
- GUI: pannello **“Perché simile?”** in Detail e Editor (`SimilarPanel`).
- CLI: `lele similar --explain`, `lele suggest --explain`.
- **Export search → Markdown (Fase 4.2, #87):** `POST /export/search` (`text/markdown` o JSON), `core/export.py`.
- GUI: **Esporta .md** in Browse; export per bucket in Timeline.
- CLI: `lele export --search "…" --topic python -o results.md`.
- **Playwright E2E smoke (Fase 4.3):** `npm run test:e2e`, fixture `scripts/e2e-prepare.py`, job CI `e2e`.
- Test: `test_api_similar_explain.py`, `test_export_search.py`, `frontend/e2e/smoke.spec.ts`.

### Changed
- CI: tre job (`test`, `e2e`, `packaging-smoke`).

### Docs
- `docs/gui-design.md`: sezione Fase 4.
- `docs/phase-4-issue.md`: tracking Fase 4 completo.
- README: endpoint export, explain, Test E2E.

## [1.8.0] - 2026-07-05

### Added
- `core/analytics.py` — statistiche e timeline da dataset JSONL.
- API: `GET /stats/summary`, `GET /stats/timeline` (group_by: year/month/topic).
- GUI: viste **Stats** e **Timeline** (#88, #89).
- CLI: `lele stats`, `lele timeline --group-by month|year|topic`.
- Test `test_analytics.py`, `test_api_stats_timeline.py`.

### Changed
- `GET /ui` deprecato → redirect 307 a `/app/#/`.
- Sidebar GUI: rimosso link PoC legacy.

## [1.7.0] - 2026-07-05

### Added
- `core/vault.py` — vault tree, markdown write-back, import to JSONL.
- API: `GET /vault/status`, `GET /vault/tree`, `POST /vault/import`.
- API: `POST /vault/lessons` (create `.md` in vault), `PUT /lessons/{id}` (update + sync).
- API: `POST /ops/refresh` (import vault + optional train).
- GUI Fase 2: Salva nel vault (Editor), albero vault reale, import/refresh in Ops.
- Test `tests/test_api_vault.py`.

### Changed
- Lesson routes accept slash IDs via `{lesson_id:path}` (es. `python/2026-07-05.slug`).
- Explicit `PyYAML` dependency.

## [1.6.0] - 2026-07-05

### Added
- GUI web v2.0 alpha: Vite + Svelte SPA su `GET /app/` (Browse, Detail, Editor, Vault, Ops).
- `scripts/build-gui.sh` — build frontend e copia in `src/lele_manager/gui/static`.
- `frontend/` — sorgenti Svelte (API client, hash router, suggest live).
- Test `tests/test_gui_app.py` + CI build Node prima di pytest/packaging.

### Changed
- `GET /` reindirizza a `/app/`.
- README: sezione GUI Web.
- CI: Node.js 22 + `./scripts/build-gui.sh` nei job test e packaging-smoke.

### Deprecated
- `GET /ui` — PoC legacy; usare `/app/`.

## [1.5.0] - 2026-07-05

### Added
- MIT `LICENSE` file.
- API: `POST /similar/batch` (deterministic, cache-aware).
- API: `POST /editor/suggest` thin wrapper for live similarity while writing.
- API: `explain=true` metadata on similarity endpoints.
- ML: `similarity_service` as single orchestration boundary (API + CLI).
- ML: `SimilarityBackend` abstraction (TF-IDF default).
- ML: opt-in LSA similarity backend (TF-IDF + TruncatedSVD) with determinism guardrails.

### Changed
- API: FastAPI `version` now reads from installed package metadata (`pyproject.toml`).
- API: similarity routes aligned through `similarity_service` with unified defaults.
- API: `Lesson` schema aligned with core `created_at` SSOT + deterministic ordering.
- CI: PyPI publish gated behind `PYPI_ENABLED` repository variable.

### Fixed
- API: removed duplicate `created_at` field in `LessonBase` Pydantic schema.

### Docs
- `CHANGELOG.md` backfilled for releases 1.2.0–1.4.1.
- `ROADMAP.md` aligned with current project state.

## [1.4.1] - 2026-02-15

### Added
- Release workflow enabled for tag pushes.

## [1.4.0] - 2026-02-15

### Added
- Packaging smoke test in CI (build/install wheel + `ui.html` content check).
- `ui.html` bundled in wheel via `package-data`.
- UI: free-text similarity search (`POST /similar` from `/ui`).
- Core: `SimilarityRankingConfig` for shared ranking defaults.
- ML: deterministic ranking with `lesson_id` tie-breaker.

### Changed
- Version bumped to 1.4.0.

## [1.3.2] - 2026-02-15

### Added
- Perf guardrail test for `/similar` warm-cache.
- API: in-process similarity index cache + invalidation after `POST /train/topic`.

### Changed
- API: hardened `POST /lessons/search` against `NaN`/`NaT` + deterministic ordering.

## [1.3.1] - 2026-02-15

### Docs
- Changelog updated for v1.3.0.

## [1.3.0] - 2026-02-15

_See [1.2.0] — same commit tag point; version marker for milestone tracking._

## [1.2.0] - 2026-02-15

### Added
- API: `POST /similar` endpoint for text-based similarity (no `lesson_id` required).
- API: `POST /lessons/search` advanced search with JSON payload filters.
- API: minimal web UI at `GET /ui` (search + similar panel).
- CLI: `lele suggest` command (`--text`, `--file`, stdin, `--watch`).
- CLI: `lele search`, `show`, `similar`, `train-topic` over HTTP API.
- Core: `lele_manager.core` package (`model`, `paths`, `config`, `storage`, `ranking`).
- Paths: XDG defaults via `platformdirs` (`LELE_DATA_DIR`, deprecated `LELE_DATA_PATH`).
- CI: issue/PR templates, `CODEOWNERS`.
- Release workflow scaffold (PyPI publishing deferred).

### Changed
- Internal imports repointed to `core` package; top-level shims kept for compatibility.

## [1.1.2] - 2026-02-06

### Added
- Added `CONTRIBUTING.md` with minimal contributor workflow (setup + quality gates).

### Docs
- README: link to contributing guidelines.

## [1.1.1] - 2026-02-05

### Added
- Added `CHANGELOG.md` in Keep a Changelog format with version links.

## [1.1.0] - 2026-02-01

### Added
- CLI entrypoint `lele` (developer-friendly command surface).
- Dev helper scripts for running the API quickly during local development.
- Basic tests for CLI and API (stabilization step toward CI-ready quality gates).

### Changed
- Project wiring to support the new CLI + tests lifecycle.

## [1.0.0] - 2025-12-05

### Added
- LeLe Vault (Markdown + YAML frontmatter) → import into JSONL.
- ML pipeline: topic model + similarity search.
- FastAPI endpoints: `/health`, `/lessons`, `/lessons/{id}/similar`, `/train/topic`.
- Dev script `lele-api-refresh.sh` + alias `lele-refresh`.

### Fixed
- Date parsing (YAML → JSON).
- NaN/NaT handling in the API layer.

[Unreleased]: https://github.com/gcomneno/lele-manager/compare/v1.11.1...HEAD
[1.11.1]: https://github.com/gcomneno/lele-manager/compare/v1.11.0...v1.11.1
[1.11.0]: https://github.com/gcomneno/lele-manager/compare/v1.10.1...v1.11.0
[1.10.1]: https://github.com/gcomneno/lele-manager/compare/v1.10.0...v1.10.1
[1.10.0]: https://github.com/gcomneno/lele-manager/compare/v1.9.0...v1.10.0
[1.9.0]: https://github.com/gcomneno/lele-manager/compare/v1.8.0...v1.9.0
[1.8.0]: https://github.com/gcomneno/lele-manager/compare/v1.7.0...v1.8.0
[1.7.0]: https://github.com/gcomneno/lele-manager/compare/v1.6.0...v1.7.0
[1.6.0]: https://github.com/gcomneno/lele-manager/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/gcomneno/lele-manager/compare/v1.4.1...v1.5.0
[1.4.1]: https://github.com/gcomneno/lele-manager/compare/v1.4.0...v1.4.1
[1.4.0]: https://github.com/gcomneno/lele-manager/compare/v1.3.2...v1.4.0
[1.3.2]: https://github.com/gcomneno/lele-manager/compare/v1.3.1...v1.3.2
[1.3.1]: https://github.com/gcomneno/lele-manager/compare/v1.3.0...v1.3.1
[1.3.0]: https://github.com/gcomneno/lele-manager/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/gcomneno/lele-manager/compare/v1.1.2...v1.2.0
[1.1.2]: https://github.com/gcomneno/lele-manager/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/gcomneno/lele-manager/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/gcomneno/lele-manager/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/gcomneno/lele-manager/releases/tag/v1.0.0
