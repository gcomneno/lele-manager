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
