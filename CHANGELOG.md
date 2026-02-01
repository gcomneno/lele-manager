# Changelog
All notable changes to this project will be documented in this file.

The format is based on **Keep a Changelog**, and this project adheres to **Semantic Versioning**.

## [Unreleased]

### Added
- More API tests coverage (health “present”, `/lessons/{id}` 200/404, `/similar` edge cases).
- Training API hardening: `/train/topic` returns 400 (human message) for user errors (e.g. single-topic dataset, TF-IDF empty vocabulary).
- Extra tests guarding `/train/topic` failure modes and `/similar` edge cases.

### Changed
- API normalization for `GET /lessons/{id}` (avoid Pydantic validation errors on `date` when pandas parses timestamps).

### Fixed
- Avoid 500s on predictable training failures by mapping them to 400 with readable `detail`.

## [1.1.0] - 2026-02-01

### Added
- CLI entrypoint (`lele`) for common operations.
- Dev helper script for running the API locally.
- Initial tests for CLI + search API.

## [1.0.0] - 2025-12-05

### Added
- Initial public release.
