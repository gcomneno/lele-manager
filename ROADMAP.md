# LeLe Manager — Roadmap and current status

[English](ROADMAP.md) | [Italiano](ROADMAP.it.md)

> Personal knowledge base for textual lesson learned records:
> Markdown vault → projection store / JSONL → ML (topic and similarity) →
> FastAPI API and GUI.

## 1. Project objective

LeLe Manager is the central engine for personal lesson learned records:

- lessons are authored as Markdown files organized by topic;
- LeLe Manager imports, validates, normalizes, and exposes them for:
  - full-text and filtered search;
  - topic classification;
  - similar-lesson recommendations;
  - review, export, and downstream integrations.

The target is a stable local-first daily tool with recoverable data and an ML
foundation that can evolve without becoming the source of truth.

## 2. Original steps and progress

The original roadmap consisted of:

1. **Python setup and tooling** — environment, project structure, and initial
   CLI tools.
2. **Data and exploratory analysis** — lesson format, storage, ingestion, and
   initial analysis.
3. **Classic ML** — topic classification and TF-IDF-based similarity.
4. **Pipeline and feature engineering** — shared features, scikit-learn
   pipelines, and ML CLI tools.
5. **FastAPI and end-to-end capstone** — API endpoints, development scripts,
   and later GUI integration.

### 2.1 Completed foundations

- **Python setup and tooling**
  - `src/lele_manager/` package layout;
  - `pyproject.toml`, development extras, virtual environment workflow;
  - early CLI tools such as `csv2json` and `file_watcher`;
  - pre-commit hooks for whitespace, YAML, and Ruff.

- **Lesson data and ingestion**
  - core fields: `id`, `text`, `topic`, `source`, `importance`, `tags`,
    `date`, and `title`;
  - Markdown vault input with YAML frontmatter;
  - JSONL compatibility dataset;
  - ingestion from CSV and other sources;
  - deterministic raw-source chunking and TritaLeLe candidate staging.

- **Classic ML**
  - `train_topic_model(df)` with TF-IDF and `LogisticRegression`;
  - a serialized scikit-learn pipeline in `models/topic_model.joblib`;
  - `LessonSimilarityIndex`;
  - text- and ID-based similarity;
  - optional LSA similarity backend.

- **Shared feature pipeline**
  - `LessonFeatureExtractor`;
  - text TF-IDF plus character count, word count, and `importance`;
  - `TopicModelConfig`, `build_topic_pipeline`, and hardened training errors;
  - shared behavior across topic classification and similarity.

- **LeLe Vault**
  - configurable root through `LELE_VAULT_DIR`;
  - tolerant importer input and strict canonical `lele doctor` validation;
  - canonical `topic` and `id` checks against the relative path;
  - duplicate handling with `overwrite`, `skip`, and `error`;
  - SHA-256 frontmatter hashing;
  - robust YAML date serialization;
  - Markdown write-back and vault refresh workflows.

- **FastAPI and development scripts**
  - core lesson, search, training, similarity, duplicate, analytics, export,
    vault, and operations endpoints;
  - versioned TritaLeLe candidate workflow under `/api/v1/tritalele`;
  - `scripts/lele-api-dev.sh`;
  - `scripts/lele-api-refresh.sh`;
  - GUI static serving and application composition.

- **Web GUI**
  - Svelte SPA with Browse, Detail, Editor, Vault, Ops, Timeline, and Stats;
  - live suggestions and explained similarity;
  - Markdown export;
  - vault write-back;
  - Playwright E2E smoke tests.

- **Projection-store boundary**
  - backend-neutral typed port;
  - coherent immutable snapshots;
  - deterministic ordering, counts, and content generation;
  - validated atomic whole-snapshot publication;
  - JSONL compatibility adapter;
  - explicit legacy append facade.

## 3. Current product state

LeLe Manager currently provides:

- a canonical Markdown vault for approved lesson authoring;
- a strict local knowledge doctor;
- a derived JSONL projection used by compatibility and ML flows;
- topic classification and similarity over real lesson data;
- exact- and near-duplicate reporting;
- a FastAPI server;
- an API-oriented `lele` CLI client;
- a Svelte GUI;
- TritaLeLe raw-source ingestion, candidate review, and approval workflows;
- a local PKPS v1 package consumer boundary and staging through TritaLeLe
  candidates, without pre-approval vault or projection writes;
- deterministic tests across domain, storage, API, CLI, and GUI boundaries.

The project is usable as a personal production tool, while storage migration
and a few architectural cleanups remain active work.

## 4. Completed quality and product work

### 4.1 Automated tests

Coverage includes:

- importer behavior and frontmatter repair;
- canonical vault validation and duplicate IDs;
- topic-model training success and failure modes;
- similarity service equivalence and edge cases;
- API health, search, details, similarity, analytics, export, and vault flows;
- projection-store contract behavior;
- TritaLeLe ingestion, review, approval, CLI, and API workflows;
- GUI build and Playwright smoke tests.

### 4.2 Advanced search

- `POST /lessons/search`;
- topic, source, importance, and text filters;
- normalized records and deterministic ordering;
- CLI and GUI consumers.

### 4.3 API-oriented CLI

- `lele search`;
- `lele show`;
- `lele similar`;
- `lele train-topic`;
- `lele suggest`;
- `lele export`;
- `lele duplicates`;
- `lele doctor`;
- TritaLeLe candidate commands;
- `lele pkps import PACKAGE_PATH` for versioned GYTE lesson packages;
- `LELE_API_URL` configuration where applicable.

### 4.4 Documentation and release hygiene

- Semantic Versioning;
- `CHANGELOG.md`;
- MIT license;
- contributor guide;
- English-canonical bilingual documentation policy;
- maintained English/Italian mirrors for primary user and contributor docs;
- focused documentation tests;
- release and packaging workflows.

Remaining release-hygiene work includes dependency pinning or a justified
lockfile strategy.

## 5. Active architecture direction

### 5.1 Canonical content and projections

The target separation is:

- **Markdown vault:** authoritative approved lesson content;
- **projection store:** queryable application view;
- **JSONL:** derived interoperability, fixture, export, and ML snapshot;
- **ML models:** rebuildable derived artifacts tied to a dataset generation.

The current adapter remains JSONL for compatibility. SQLite is the intended
local query backend after parity, migration, and reconciliation work described
by [ADR 0001](docs/adr/0001-storage-backend.md).

### 5.2 TritaLeLe ingestion

The target workflow is:

```text
source material
  → deterministic chunks
  → staged candidates
  → explicit human review
  → approval
  → canonical Markdown vault
  → projection refresh
  → export and ML derivatives
```

Candidates are not approved lessons. They remain isolated from the canonical
vault and ML dataset until explicit approval succeeds.

### 5.3 LeLe Manager local PKPS consumer

LeLe Manager completes its local consumer boundary for PKPS v1 packages: GYTE
exports a versioned lesson package, while LeLe validates it and stages an
ordinary TritaLeLe candidate. Package provenance is immutable and flows into
approval; canonical identity, duplicate handling, and publication remain LeLe
decisions.

This vertical slice is not the independent PKPS project, its cross-repository
orchestration, or the future canonical protocol. See the
[PKPS consumer contract](docs/pkps-package.md).

### 5.4 Documentation

English is canonical and default. Italian is officially maintained for the
document pairs listed in
[the documentation policy](docs/documentation-policy.md).

Historical records, generated artifacts, and selected technical sources are
excluded only through an explicit classification and rationale.

## 6. Practical priorities

1. **Keep the current system stable**
   - preserve deterministic domain and storage contracts;
   - maintain green lint, typing, tests, packaging, security, and E2E checks;
   - keep documentation pairs synchronized.

2. **Complete storage evolution**
   - reconcile vault-only and JSONL-only records;
   - introduce and validate the SQLite adapter;
   - prove parity with the JSONL compatibility backend;
   - expose stale projection state explicitly;
   - cut over gradually without creating a second authority.

3. **Complete TritaLeLe product integration**
   - connect the candidate workflow to the GUI;
   - preserve explicit review and approval;
   - keep provenance and failure recovery visible;
   - avoid direct candidate promotion into canonical datasets.

4. **Improve maintainability**
   - split oversized FastAPI modules into focused routers and services;
   - define dependency pinning or lockfile policy;
   - keep boundaries between authoring, synchronization, projection, export,
     and ML explicit.

5. **Expand integrations when justified**
   - editor integrations such as VS Code or Obsidian;
   - external quiz and review consumers;
   - richer embeddings or ranking only after measurable benefit;
   - analytical tooling such as DuckDB only for a demonstrated workload.

## 7. Nice-to-have research

- alternative dense embeddings or hybrid retrieval;
- personalized revisit-priority ranking;
- richer explainability for similarity and duplicate detection;
- editor-native workflows;
- versioned external lesson contracts;
- analytics over larger exported snapshots.

These items must not weaken local-first recoverability, deterministic behavior,
or the authority of reviewed Markdown content.

## 8. Explicit non-priorities

The current project does not need:

- a distributed database;
- a remote document-store service;
- unreviewed automatic candidate approval;
- opaque automatic translation;
- a heavy documentation platform;
- infrastructure that exceeds the scale of the personal local-first workload.
