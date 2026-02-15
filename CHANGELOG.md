# Changelog

All notable changes to **LeLe Manager** will be documented in this file.

This project follows **Semantic Versioning** (`MAJOR.MINOR.PATCH`):
- **MAJOR**: breaking changes (API / formats)
- **MINOR**: backward-compatible features
- **PATCH**: bugfix / internal improvements

The format is based on **Keep a Changelog**.

## [1.3.0] - 2026-02-15

### Added
- Tests: add a basic performance guardrail for `POST /similar` (warm cache must be faster than cold).
- Tests: register custom pytest marker `perf`.

### Changed
- API: cache `LessonSimilarityIndex` in API layer (reuse across requests).
- CLI: improve `lele suggest --watch` UX (debounce, no-spam, clean Ctrl+C stop).

### Fixed
- API: harden `/lessons/search` against NaN/NaT edge cases (avoid false matches caused by `"nan"`).
- API: add deterministic ordering to `/lessons/search` (importance desc, date desc, id asc).
- API: invalidate similarity cache after `/train/topic`.

### Added
- API: `POST /similar` endpoint for text-based similarity (no lesson_id required).
- CLI: `lele suggest` command (supports --text, --file, stdin, --watch).


### Changed
- (placeholder)

### Fixed
- (placeholder)

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

[Unreleased]: https://github.com/gcomneno/lele-manager/compare/v1.3.0...HEAD
[1.3.0]: https://github.com/gcomneno/lele-manager/compare/v1.2.0...v1.3.0
[1.1.2]: https://github.com/gcomneno/lele-manager/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/gcomneno/lele-manager/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/gcomneno/lele-manager/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/gcomneno/lele-manager/releases/tag/v1.0.0
