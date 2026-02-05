# Changelog
All notable changes to **LeLe Manager** will be documented in this file.

This project follows **Semantic Versioning** (`MAJOR.MINOR.PATCH`):
- **MAJOR**: breaking changes (API / formats)
- **MINOR**: backward-compatible features
- **PATCH**: bugfix / internal improvements

The format is based on **Keep a Changelog**.

## [Unreleased]

### Added
- (placeholder)

### Changed
- (placeholder)

### Fixed
- (placeholder)

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

[Unreleased]: https://github.com/gcomneno/lele-manager/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/gcomneno/lele-manager/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/gcomneno/lele-manager/releases/tag/v1.0.0
