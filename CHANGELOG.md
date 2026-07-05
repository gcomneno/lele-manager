# Changelog

All notable changes to **LeLe Manager** will be documented in this file.

This project follows **Semantic Versioning** (`MAJOR.MINOR.PATCH`):
- **MAJOR**: breaking changes (API / formats)
- **MINOR**: backward-compatible features
- **PATCH**: bugfix / internal improvements

The format is based on **Keep a Changelog**.

## [Unreleased]

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

[Unreleased]: https://github.com/gcomneno/lele-manager/compare/v1.6.0...HEAD
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
