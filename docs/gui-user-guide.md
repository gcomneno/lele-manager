# LeLe Manager GUI user guide

[English](gui-user-guide.md) | [Italiano](it/gui-user-guide.md)

> Status: maintained user documentation
> Related issue: [#112](https://github.com/gcomneno/lele-manager/issues/112)

This guide documents the released local web GUI. The historical design record
remains in [`gui-design.md`](gui-design.md).

## Start the GUI

The normal local workflow is:

```bash
export LELE_VAULT_DIR="$HOME/LeLeVault"
./scripts/build-gui.sh
./scripts/lele-api-dev.sh
```

Open:

```text
http://127.0.0.1:8000/app/
```

Use `scripts/lele-api-refresh.sh` instead when the Markdown vault must first be
imported and the topic model retrained.

## GUI language

LeLe Manager starts in **English** when no explicit language choice is stored.
The language selector is in the sidebar, immediately above the GiadaWare
signature. The maintained GUI languages are **English** and **Italiano**.

Changing language updates the GUI immediately without reloading the page. The
explicit choice is stored locally in the browser under
`lele-manager.locale`. Missing, malformed or unsupported stored values fall
back safely to English; browser-language auto-detection is intentionally not
used.

GUI localization affects product presentation only. It does not translate or
modify user-authored LeLe, Markdown vault content, dataset values, topic names,
source names, paths, IDs, API payloads or navigation identities.

## Daily workflow

1. Check health and vault diagnostics in **Ops**.
2. Browse, filter and inspect existing lessons.
3. Create or edit approved lessons through **Editor**.
4. Review exact and near duplicates through **Duplicates**.
5. Ingest raw notes through **TritaLeLe**, keeping preview, staging, review and
   approval as separate actions.
6. Use **Vault**, **Stats** and **Timeline** to inspect the resulting knowledge
   base.

## GUI views

| View | Purpose |
|---|---|
| Browse | Search, filter and export lessons |
| Detail | Read one lesson and inspect explained similarity |
| Editor | Create or update canonical Markdown lessons |
| Timeline | Inspect lessons by month, year or topic |
| Stats | Inspect counts, topics, tags and averages |
| TritaLeLe | Preview, stage, review and explicitly approve candidates |
| Vault | Inspect the canonical Markdown tree and trigger projection import |
| Duplicates | Review duplicate and near-duplicate pairs without mutation |
| Ops | Inspect health, run Vault Doctor, import, train and refresh |

## Screenshots

The screenshots in [`images/gui/`](images/gui/) are generated from the isolated
Playwright fixture. They contain no personal vault or runtime data.

### Browse and lesson detail

![Browse view with isolated sample lessons](images/gui/browse.png)

![Lesson detail with explained similarity](images/gui/detail.png)

### Authoring and analysis

![Editor with live similarity suggestions](images/gui/editor.png)

![Statistics dashboard](images/gui/stats.png)

![Knowledge-acquisition timeline](images/gui/timeline.png)

### Vault operations and review workflows

![Canonical Markdown vault tree](images/gui/vault.png)

![Read-only duplicate review](images/gui/duplicates.png)

![Operations panel and healthy Vault Doctor report](images/gui/ops.png)

![TritaLeLe deterministic ingestion preview](images/gui/tritalele.png)

## Data model and locations

LeLe Manager separates authoritative content, persistent application data and
rebuildable artifacts.

| Layer | Default or configuration | Role | Backup priority |
|---|---|---|---|
| Markdown vault | `LELE_VAULT_DIR`, default `~/LeLeVault` | Authority for approved lessons | Critical |
| Lesson projection | `LELE_DATA_DIR/lessons.jsonl` | Rebuildable read projection | Optional |
| Candidate staging | `LELE_DATA_DIR/candidates.json` | Unapproved TritaLeLe workflow state | Important while reviews are pending |
| Topic model | `LELE_CACHE_DIR/topic_model.joblib` | Rebuildable ML artifact | Optional |
| Legacy lesson path | `LELE_DATA_PATH` | Deprecated file-level override | Migration only |
| Legacy model path | `LELE_MODEL_PATH` | Deprecated file-level override | Migration only |

Without directory overrides, application data and cache use the operating
system locations selected by `platformdirs`.

### Development-script compatibility

The maintained directory-level configuration is `LELE_DATA_DIR` and
`LELE_CACHE_DIR`. The current development scripts still set the deprecated
file-level variables `LELE_DATA_PATH=data/lessons.jsonl` and
`LELE_MODEL_PATH=models/topic_model.joblib` so development runs remain
repository-local.

This compatibility behavior is temporary. Explicit directory-level variables
should be preferred in services, custom launchers and future packaging. Do not
set both the directory-level and corresponding legacy file-level variable
unless the legacy file override is intentionally required.

## Backup and restore

### Minimum safe backup

Back up:

1. the complete Markdown vault;
2. `candidates.json` when staged candidates or review history must be retained;
3. configuration or service files that define custom environment variables.

The JSONL projection and topic model can be rebuilt from the vault.

### Restore

1. restore the Markdown vault;
2. set `LELE_VAULT_DIR` to the restored directory;
3. optionally restore `candidates.json` under `LELE_DATA_DIR`;
4. run `lele doctor`;
5. run `scripts/lele-api-refresh.sh`;
6. verify **Ops**, **Browse** and **Vault** before resuming edits.

Never replace a newer vault with an older JSONL projection. The Markdown vault
wins.

## Troubleshooting

### GUI returns HTTP 503

The frontend build is missing. Run:

```bash
./scripts/build-gui.sh
```

Then restart the API.

### Vault not found

Create the configured directory or set:

```bash
export LELE_VAULT_DIR="/absolute/path/to/LeLeVault"
```

### Dataset or model unavailable

Run the complete refresh:

```bash
./scripts/lele-api-refresh.sh
```

### Vault Doctor reports errors

Do not overwrite the projection as a substitute for fixing canonical Markdown.
Inspect the diagnostic code and affected file, correct the vault, rerun Doctor
and only then refresh derived data.

### TritaLeLe reports partial refresh

The canonical vault write may already have succeeded. Use the separate lesson
and vault read-backs shown by the GUI, inspect the reported destination, then
retry the derived refresh. Do not approve the same candidate blindly.

### Duplicate review cannot load the model

Use exact-only review when semantic near-duplicate detection is temporarily
unavailable, or rebuild the topic model.

## Packaging decision

LeLe Manager remains a local FastAPI/Svelte web application. See
[ADR 0002](adr/0002-gui-packaging.md) for the evaluated alternatives and
consequences.
