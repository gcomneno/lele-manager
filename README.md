# LeLe Manager 🐒 — Lesson-Learned Manager

[English](README.md) | [Italiano](README.it.md)

[![Security](https://github.com/gcomneno/lele-manager/actions/workflows/security.yml/badge.svg)](https://github.com/gcomneno/lele-manager/actions/workflows/security.yml)
[![CI](https://github.com/gcomneno/lele-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/gcomneno/lele-manager/actions/workflows/ci.yml)

LeLe Manager is an end-to-end local-first system for collecting, validating,
searching, and reusing textual lesson learned records.

A lesson combines Markdown content with stable metadata. LeLe Manager can:

- collect lessons through Markdown, CLI, GUI, and API workflows;
- search by text, topic, source, date, importance, and tags;
- find exact duplicates, near duplicates, and related lessons;
- train a topic model and reuse the same feature pipeline for similarity;
- preserve an inspectable Markdown vault while publishing derived datasets and
  models.

English is the canonical documentation language. See the
[documentation language policy](docs/documentation-policy.md).

## Quality gates

- **CI:** `ruff check .`, `mypy src/lele_manager`, `pytest`, packaging smoke,
  and Playwright E2E smoke with Python 3.12 and Node.js 22.
- **Security:** `pip-audit` and `bandit` through GitHub Actions.
- **pre-commit:** whitespace and end-of-file cleanup, `check-yaml`, and `ruff`.
- **Documentation:** required bilingual pairs, reciprocal language selectors,
  same-language root navigation, and relative links.

Run the documentation checks with:

```bash
pytest tests/test_documentation.py
```

## Project links

- Full roadmap: [ROADMAP.md](ROADMAP.md)
- Changelog: [CHANGELOG.md](CHANGELOG.md)
- Contributor guide: [CONTRIBUTING.md](CONTRIBUTING.md)
- Documentation policy: [docs/documentation-policy.md](docs/documentation-policy.md)
- GUI user guide: [docs/gui-user-guide.md](docs/gui-user-guide.md)
- Projection-store contract:
  [docs/projection-store.md](docs/projection-store.md)
- LeLe Manager PKPS consumer contract:
  [docs/pkps-package.md](docs/pkps-package.md)

## Main goals

- Fast lesson collection through CLI and API.
- Stable metadata: date, source, topic, importance, tags, and title.
- Full-text and filtered search.
- Similarity recommendations while writing or reviewing.
- Local-first Markdown authoring with derived JSONL and ML artifacts.
- Progressive automation for classification and ranking without making user
  data opaque or difficult to recover.

## Technical stack

- Python **3.12** in CI; also tested with Python 3.13.
- `pandas` and `numpy` for data processing.
- `scikit-learn` for TF-IDF, classification, and similarity.
- FastAPI and Uvicorn for the HTTP API.
- Svelte, TypeScript, and Vite for the web GUI.
- A backend-neutral projection-store port with JSONL as the current
  compatibility adapter. SQLite remains a later migration target; see
  [the projection-store contract](docs/projection-store.md) and
  [ADR 0001](docs/adr/0001-storage-backend.md).

## Install and run

For normal end-user use, download the native package for your operating system
from GitHub Releases, extract it, and launch **LeLe-Manager**. The native
packages for Linux, macOS, and Windows are self-contained: they do not require
Python, Node.js, npm, a virtual environment, or a repository checkout.

### Linux: portable or user-local installed

The Linux `.tar.gz` remains a portable extract-and-run release: launch
`LeLe-Manager/LeLe-Manager` directly from the extracted archive and keep or
move that directory as you prefer.

It also includes an explicit user-local installer. From the extracted archive
root, run:

```bash
./install.sh
```

This copies the native bundle to
`${XDG_DATA_HOME:-~/.local/share}/lele-manager/install/app` and creates the stable
`~/.local/bin/lele-manager` launcher, an application-menu entry at
`${XDG_DATA_HOME:-~/.local/share}/applications/lele-manager.desktop`, and the
official icon at `${XDG_DATA_HOME:-~/.local/share}/icons/hicolor/scalable/apps/lele-manager.svg`.
The menu entry always launches the stable launcher, so it is suitable for normal
favorites or dock pinning and survives application upgrades. The launcher is
intended for a user whose `~/.local/bin` is on `PATH`; the installer prints the
exact path when it is not. Advanced users and automated environments may choose
another absolute launcher directory with `LELE_MANAGER_INSTALL_BIN_DIR`.
Launcher paths containing spaces are supported; newline characters are rejected
because they cannot be represented in a desktop-entry command line.

`${XDG_DATA_HOME:-~/.local/share}/lele-manager/` is the persistent runtime-data
namespace; only its `install/` subtree is installer-owned and replaceable.
Re-running `./install.sh` from a newer extracted Linux release replaces only
the stable `install/app/` bundle and refreshes its product-owned desktop entry
and icon. It does not remove the existing data, vault, or model paths. Portable
extract-and-run mode does not register any desktop resources.

On first launch, LeLe Manager prepares its local application directories and
default Markdown vault outside the installation directory, starts the local
FastAPI application, waits for it to become healthy, and opens `/app/` in the
default browser. Persistent user data therefore survives replacing or upgrading
the extracted application package.

Each native archive includes `LEGGIMI_PRIMA.txt` with platform-specific
first-run instructions.

For Python and power users, LeLe Manager is also published on PyPI. Install it
as an isolated application with `pipx`:

```bash
pipx install lele-manager
```

The PyPI package exposes both `lele-manager` for the local application launcher
and `lele` for the CLI. Native GitHub Release packages remain the recommended
installation path for normal end-user use.

For development from source, clone the repository and create a virtual
environment:

```bash
git clone git@github.com:gcomneno/lele-manager.git
cd lele-manager

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -e .[dev]
```

Run the Python static checks and tests:

```bash
ruff check .
mypy src/lele_manager
pytest
```

## First CLI tools

The original module-level tools remain available:

```bash
# Convert a lesson CSV file to JSON
python -m lele_manager.cli.csv2json samples/input.csv samples/output.json

# Watch a directory for new files
python -m lele_manager.cli.file_watcher data

# Import Markdown lessons with YAML frontmatter from a vault
python -m lele_manager.cli.import_from_dir \
  "$LELE_VAULT_DIR" \
  data/lessons.jsonl \
  --on-duplicate overwrite \
  --default-source note \
  --default-importance 3 \
  --write-missing-frontmatter
```

## Quick lesson workflow through the legacy CLI

Add a lesson:

```bash
python -m lele_manager.cli.add_lesson \
  --text "With a src layout I must configure PYTHONPATH or use a conftest for pytest." \
  --source chatgpt \
  --topic python \
  --importance 4 \
  --tags "python,pytest,tooling"
```

Main fields:

- `text`: lesson content;
- `source`: origin such as `chatgpt`, `book`, `experiment`, or `note`;
- `topic`: primary topic such as `python`, `ml`, `linux`, or `writing`;
- `importance`: numeric importance, normally from 1 to 5;
- `tags`: comma-separated tags.

List lessons:

```bash
python -m lele_manager.cli.list_lessons --limit 10
```

## LeLe Vault: Markdown and YAML frontmatter

LeLe Manager supports a Markdown vault as the authoring surface for approved
lessons.

A typical flow is:

- write and organize `.md` files under a directory such as `~/LeLeVault`;
- import and normalize them into `data/lessons.jsonl`;
- train or refresh derived models;
- query them through CLI, API, or GUI.

The lesson ID lives in frontmatter. In the canonical vault contract, identity
and location are aligned: `topic` matches the first relative directory and
`id` matches the relative path without `.md`. Renaming or moving a canonical
file therefore requires updating its identity metadata.

### Recommended vault structure

```text
LeLeVault/
  python/
    2025-11-20.pytest-src-layout.md
  cpp/
    2025-11-20.cin-vs-getline.md
  linux/
    2025-11-20.rsync-dry-run-backup.md
  writing/
    2025-11-22.show-dont-tell.md
```

Soft filename conventions:

- directory name = primary topic;
- filename = `YYYY-MM-DD.slug.md`;
- use `.` and `-`, not `_`, in the slug.

### Importer input schema

A lesson may start with YAML frontmatter:

```markdown
---
id: cpp/2025-11-20.cin-vs-getline
topic: cpp
source: book
importance: 4
tags: [cpp, io, strings]
date: 2025-11-20
title: "LL-5 — std::cin vs std::getline"
lifecycle: deprecated
superseded_by: cpp/2026-08-15.input-handling
---
```

The importer accepts a tolerant input schema:

- `id` is optional and may be derived from the relative path;
- `topic` may be read from frontmatter, `--default-topic`, or the directory;
- `source` identifies the origin;
- `importance` is normally an integer from 1 to 5;
- `tags` may be a list or a comma-separated string;
- `date` is ISO-like and may be derived from the filename;
- `title` is optional for importer input;
- `lifecycle` is optional and accepts `active`, `review-needed`, `deprecated`,
  or `archived`; absence means `active`;
- `superseded_by` is optional and identifies one maintained replacement by
  stable lesson ID.

Lifecycle changes are explicit canonical edits. Derived signals such as
similarity, freshness, or contradiction detection may suggest review, but never
change lifecycle automatically. Supersession also never deletes canonical
content or changes lifecycle implicitly.

LeLe Manager also calculates `frontmatter_hash` for diagnostics and
versioning. The identity remains `id`.

Importer tolerance does not mean every importable file satisfies the canonical
`doctor` contract.

### Canonical schema validated by `lele doctor`

`lele doctor` requires all seven fields:

- `id`;
- `topic`;
- `source`;
- `importance`;
- `tags`;
- `date`;
- `title`.

`id`, `topic`, `source`, and `title` must be non-empty strings.
`importance` must be an integer from 1 to 5. `date` must be a valid
`YYYY-MM-DD` date. `tags` must be a non-empty list of non-empty strings. The
Markdown body must also be non-empty.

When a vault context is available, selected files must remain inside the vault
after symlink resolution. `topic` must match the first relative directory and
`id` must match the full relative path without `.md`.

### Validate a vault

```bash
# Recursively validate the vault configured through LELE_VAULT_DIR
lele doctor

# Validate a specific vault
lele doctor --vault /path/to/LeLeVault

# Validate selected files using the configured vault as context
lele doctor "$LELE_VAULT_DIR/python/2026-07-13.example.md"

# Produce script-friendly JSON
lele doctor --json
```

`lele doctor` reads Markdown without intentionally rewriting content,
timestamps, or permissions. Filesystem access may still update access time.

Exit codes:

- `0`: valid report;
- `1`: validation errors;
- `2`: operational or usage error, including a selected file outside the
  configured vault.

### Import Markdown to JSONL

```bash
python -m lele_manager.cli.import_from_dir \
  "$LELE_VAULT_DIR" \
  data/lessons.jsonl \
  --on-duplicate overwrite \
  --default-source note \
  --default-importance 3 \
  --write-missing-frontmatter
```

The importer:

- scans recursively for `.md` files;
- reads frontmatter and body;
- derives a missing ID from the relative path;
- derives or normalizes topic, tags, importance, and date;
- calculates `frontmatter_hash`;
- builds an in-memory `id -> record` map;
- publishes a complete JSONL snapshot with one record per unique ID.

`--write-missing-frontmatter` repairs only missing or invalid input fields.
Valid complete frontmatter is not rewritten merely to normalize JSONL output.

Duplicate behavior is selected with:

- `--on-duplicate overwrite`: the last scanned record wins;
- `--on-duplicate skip`: the first record wins;
- `--on-duplicate error`: stop at the first duplicate ID.

### Recommended refresh flow

1. Write or organize Markdown lessons in `$LELE_VAULT_DIR`.
2. Import the vault.
3. Train the topic model.
4. Query the archive.

```bash
python -m lele_manager.cli.import_from_dir \
  "$LELE_VAULT_DIR" \
  data/lessons.jsonl \
  --on-duplicate overwrite \
  --write-missing-frontmatter

python -m lele_manager.cli.train_topic_model \
  --input data/lessons.jsonl \
  --output models/topic_model.joblib \
  --overwrite

python -m lele_manager.cli.suggest_similar \
  --input data/lessons.jsonl \
  --model models/topic_model.joblib \
  --text "When std::cin reads a string, input is truncated at whitespace" \
  --top-k 5 \
  --min-score 0.1
```

## Topic model and similarity

`train_topic_model(df)` builds a scikit-learn pipeline using TF-IDF features
and `LogisticRegression`.

`LessonFeatureExtractor` combines:

- TF-IDF features from lesson text;
- character length;
- word count;
- `importance`, when available.

The same feature representation supports topic classification and similarity.

`LessonSimilarityIndex.from_lessons(...)` and
`LessonSimilarityIndex.from_topic_pipeline(...)` build the similarity index.
`most_similar(query_text, top_k)` returns lesson IDs and cosine scores.

### Train through the module CLI

```bash
python -m lele_manager.cli.train_topic_model \
  --input data/lessons.jsonl \
  --output models/topic_model.joblib \
  --overwrite
```

The JSONL input must contain at least `text` and `topic`.

```json
{"id": "89c6bca8-941b-4a93-a7ca-a35e584ae5ec",
 "text": "With a src layout I must manage PYTHONPATH or use a conftest for pytest.",
 "topic": "python",
 "source": "chatgpt",
 "importance": 4,
 "tags": ["python", "pytest", "tooling"]}
```

The complete pipeline is stored in `models/topic_model.joblib`.

### Find similar lessons through the module CLI

Free-text query:

```bash
python -m lele_manager.cli.suggest_similar \
  --input data/lessons.jsonl \
  --model models/topic_model.joblib \
  --text "With a src layout I must configure PYTHONPATH or use a conftest for pytest." \
  --top-k 5 \
  --min-score 0.1
```

Query by an existing lesson ID:

```bash
python -m lele_manager.cli.suggest_similar \
  --input data/lessons.jsonl \
  --model models/topic_model.joblib \
  --from-id "89c6bca8-941b-4a93-a7ca-a35e584ae5ec" \
  --id-column id \
  --top-k 5 \
  --min-score 0.1
```

Output includes the lesson ID, similarity score, and a text preview.

## Security and pre-commit

The security workflow runs on pushes, pull requests, and a weekly schedule:

- `pip-audit` checks Python dependencies;
- `bandit` checks Python code under `src/`.

Install local pre-commit hooks with:

```bash
pip install pre-commit
pre-commit install
```

The configuration provides whitespace and final-newline cleanup, YAML
validation, and Ruff checks.

## Local data and models

- Personal lesson data lives under `data/`.
- Trained models live under `models/`.
- Both directories are excluded from version control.

The public repository therefore does not contain the personal vault, derived
dataset, or trained models.

## Utility scripts

### Full refresh: `scripts/lele-api-refresh.sh`

The complete development refresh:

1. imports `$LELE_VAULT_DIR` into `data/lessons.jsonl`;
2. retrains `models/topic_model.joblib`;
3. starts the FastAPI server with Uvicorn `--reload`.

```bash
cd ~/Projects/lele-manager
export LELE_VAULT_DIR=/home/user/LeLeVault
./scripts/lele-api-refresh.sh
```

### API only: `scripts/lele-api-dev.sh`

Use this when dataset and model are already ready:

```bash
cd ~/Projects/lele-manager
./scripts/lele-api-dev.sh
```

The script locates the project root, activates `.venv`, checks for Uvicorn, and
starts the server on `http://127.0.0.1:8000`.

## FastAPI API

Main endpoints include:

- `GET /health`;
- `GET /lessons`;
- `GET /lessons/{id}`;
- `GET /lessons/{id}/similar`;
- `GET /duplicates`;
- `POST /similar`;
- `POST /editor/suggest`;
- `POST /export/search`;
- `GET /stats/summary`;
- `GET /stats/timeline`;
- `POST /train/topic`;
- `POST /lessons/search`.

Similarity endpoints accept `explain=true` where documented to include rank,
topic, and shared-tag metadata.

The versioned TritaLeLe candidate workflow is exposed below
`/api/v1/tritalele`.

Start the full flow with:

```bash
./scripts/lele-api-refresh.sh
```

Or start only the API with:

```bash
./scripts/lele-api-dev.sh
```

## Web GUI

For the complete startup, daily-use, backup, restore and troubleshooting
workflow, see the [GUI user guide](docs/gui-user-guide.md).

Build the Svelte frontend and start the API:

```bash
./scripts/build-gui.sh
./scripts/lele-api-dev.sh
# Open http://127.0.0.1:8000/app/
```

Available views:

| View | Purpose |
|---|---|
| **Dashboard** | Workspace readiness, bounded knowledge summary, and next useful actions |
| **Browse** | Advanced search, lifecycle filtering, and Markdown export |
| **Detail** | Full lesson content, lifecycle, supersession links, and explained similarity |
| **Editor** | Canonical Markdown authoring with explicit lifecycle and supersession controls |
| **TritaLeLe** | Controlled candidate ingestion, review, rejection, and approval |
| **Duplicates** | Read-only review of exact and near-duplicate pairs |
| **Timeline** | Knowledge-acquisition timeline and bucket export |
| **Stats** | Counts, tags, topics, and averages |
| **Vault** | Real filesystem tree and import |
| **Ops** | Health, training, vault import, and full refresh |
| **Diagnostics** | Support status, explicit bounded diagnostics, and secondary runtime paths |
| **About** | Product identity, version, MIT license, local-first statement, and support links |

Saving from the Editor writes the Markdown file into the vault and refreshes
the JSONL projection through `PUT` or `POST /vault/lessons`.

Browse, search, and export use active lessons by default. The lifecycle selector
can explicitly scope results to `review-needed`, `deprecated`, `archived`, or
all states. Non-active lessons are visually distinguished. Detail remains
addressable by stable ID regardless of lifecycle and exposes both the canonical
forward `superseded_by` relation and derived reverse supersession links where
available.

The Editor is the explicit lifecycle mutation surface: selecting Active removes
a previous non-active marker, and clearing Superseded by removes the canonical
replacement link. Neither operation deletes lesson content.

The GUI requires `LELE_VAULT_DIR`; the default is `~/LeLeVault`.

Opening `/app/` now lands on the **Dashboard**. Browse remains directly
available at `#/browse`. The Dashboard reports bounded, read-only workspace
readiness and delegates explicit maintenance or mutation to the existing
views.

### TritaLeLe workflow

Open `#/tritalele` to ingest pasted text or a Markdown/plain-text file through
the deterministic candidate workflow:

1. **Preview** computes chunks and candidate identities without writing staging,
   the canonical vault, or the JSONL projection.
2. **Stage** persists only missing candidates. Any source change invalidates the
   previous preview.
3. **Review** allows explicit text and metadata revisions using optimistic
   `expected_revision` checks. Accept moves a candidate into review; reject
   keeps it traceable in staging with its reason and history.
4. **Approve** requires a separate confirmation dialog showing the candidate,
   revision, canonical lesson ID, and destination path. Those destination values
   are calculated by the backend using the same canonicalization used during
   publication.
5. **Read-back** reports vault-write and projection-refresh outcomes separately,
   including controlled partial-success cases.

Preview, staging, revision, acceptance, and rejection never publish a lesson.
Only explicit approval may write one canonical Markdown lesson and refresh the
derived projection.

### LeLe Manager PKPS package consumer

LeLe Manager implements only the local consumer side of the PKPS protocol.
GYTE Study Tools can hand a reviewed lesson to the existing TritaLeLe boundary
without exposing its workspace:

```bash
lele pkps import PACKAGE_PATH
lele pkps import PACKAGE_PATH --json
```

The v1 import accepts a package directory or a single-root ZIP, validates its
manifest, path confinement, UTF-8 lesson, byte count, and SHA-256, then stages
one candidate. Re-importing an unchanged `package_id` and hash is idempotent;
a reused package ID with another hash is rejected. No vault, projection, or ML
write happens before the existing explicit approval. This boundary is
not the complete PKPS project or a cross-repository orchestrator. See the
[PKPS consumer contract](docs/pkps-package.md).

The completed design record remains available in Italian at
[`docs/gui-design.md`](docs/gui-design.md). It is classified as a historical
design document rather than a maintained bilingual manual.

### Frontend development

```bash
cd frontend
npm install
npm run dev
```

Use the URL printed by Vite. The development configuration proxies the API when
configured.

### Playwright E2E smoke

```bash
./scripts/build-gui.sh

cd frontend
npm install
npx playwright install chromium
npm run test:e2e
```

`scripts/e2e-serve.sh` rebuilds the current frontend, resets only
`.e2e-fixture/`, and starts Uvicorn on port `8765`. The isolated runtime uses
`.e2e-fixture/data`, `.e2e-fixture/cache`, and `.e2e-fixture/vault`, so the E2E
suite cannot inspect or mutate personal candidate staging, datasets, caches, or
vault files. CI runs the same flows after the Python checks.

## Versioning and releases

LeLe Manager follows Semantic Versioning:

- MAJOR: incompatible API or format changes;
- MINOR: backward-compatible features;
- PATCH: bug fixes and internal improvements.

A stable release includes vault import, JSONL projection, topic and similarity
models, FastAPI endpoints, the `lele` client, the packaged GUI, and green Python,
frontend, security, packaging, and native-release verification.

Native release archives are verified after packaging and before upload by
extracting the published-style artifact, starting its packaged executable on
loopback with isolated runtime directories, checking health, GUI, license,
About and Diagnostics/runtime surfaces, and confirming persistent paths remain
outside the extracted application package.

Example annotated tag:

```bash
git tag -a v1.0.0 -m "LeLe Manager 1.0.0 — first stable release"
git push origin v1.0.0
```

## Real usage flows

### Add a Git lesson and inspect suggestions

1. Create a Markdown lesson under a path such as
   `~/LeLeVault/git/2025-12-05.local-remote-architecture.md`.
2. Run:

   ```bash
   ./scripts/lele-api-refresh.sh
   ```

3. Search:

   ```bash
   lele search git --topic git --limit 5
   ```

4. Find similar lessons:

   ```bash
   lele similar "git/2025-12-05.local-remote-architecture" --top-k 5
   ```

### Update an existing lesson

1. Edit its Markdown body or frontmatter while preserving a coherent canonical
   path, `id`, and `topic`.
2. Run `./scripts/lele-api-refresh.sh`.
3. The JSONL snapshot, topic model, and API are refreshed.
4. `/lessons`, `/lessons/{id}/similar`, and `lele similar` use the new content.

### Query LeLe Manager from another project

Start the API:

```bash
cd ~/Projects/lele-manager
./scripts/lele-api-dev.sh
```

Then query it:

```bash
curl -s "http://127.0.0.1:8000/lessons/search" \
  -H "Content-Type: application/json" \
  -d '{"q": "git", "topic_in": ["git"], "limit": 5}'
```

The external project may also use `lele` when it is on `PATH`, or
`python -m lele_manager.cli.lele`.

## `lele` API client

```bash
lele --help
```

### Suggest while writing

```bash
lele suggest --text "When std::cin reads a string, input is truncated at whitespace"
lele suggest --file note.md
cat note.md | lele suggest
lele suggest --watch note.md --every 2
```

### Export search results to Markdown

```bash
lele export --search "pytest" --topic python -o results.md
lele export --search "git" -o git-lessons.md --no-frontmatter
```

### Detect duplicates and near duplicates

```bash
lele duplicates
lele duplicates --min-score 0.90 --limit 100
lele duplicates --exact-only
lele duplicates --json
```

Exact duplicates include repeated IDs and text equal after conservative Unicode,
line-ending, and trailing-space normalization. Near duplicates are non-exact
pairs whose cosine score reaches `--min-score` using the fitted similarity
feature extractor.

Topic, title, source, date, and shared tags are explanatory signals; they do not
make a pair a near duplicate by themselves. The default threshold `0.85` is
heuristic and configurable.

The trained model is required for near-duplicate detection.
`--exact-only` works without a model. Global comparison has quadratic time and
memory cost and targets the current personal dataset, not very large
collections.

### Explain similarity

```bash
lele similar "python/2025-01-01.slug" --explain
lele suggest --text "pytest fixtures" --explain
```

Common options:

- `--top-k`: maximum result count, default 5;
- `--min-score`: minimum similarity score, default 0.1;
- `--json`: raw JSON output.

The API client uses `http://127.0.0.1:8000` by default. Start
`./scripts/lele-api-dev.sh` before using it.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
