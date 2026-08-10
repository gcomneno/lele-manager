# LeLe Manager GUI user guide

[English](gui-user-guide.md) | [Italiano](it/gui-user-guide.md)

> Status: maintained user documentation
> Related issue: [#112](https://github.com/gcomneno/lele-manager/issues/112)

This guide documents the released local web GUI. The historical design record
remains in [`gui-design.md`](gui-design.md).

## Start the GUI

For normal installed-product use, download and extract the native package for
Linux, macOS, or Windows and launch **LeLe-Manager** from the extracted
`LeLe-Manager` directory. No Python, Node.js, npm, virtual environment, frontend
build, or repository checkout is required. The packaged launcher prepares local
runtime directories, starts the loopback application, waits for `/health`, and
opens `/app/` automatically.

The Linux archive also supports an explicit user-local installation: run its
top-level `./install.sh`, then start the stable `lele-manager` launcher from
`~/.local/bin` (or the documented custom bin directory). The extracted archive
continues to work portably. This installation does not yet add an application
menu entry or desktop icon.

Each native archive includes `LEGGIMI_PRIMA.txt` with platform-specific
first-run instructions.

For development from a repository checkout, use:

```bash
export LELE_VAULT_DIR="$HOME/LeLeVault"
./scripts/build-gui.sh
./scripts/lele-api-dev.sh
```

Then open:

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

1. Open **Dashboard** to see workspace readiness, attention points and the next
   useful action.
2. Use **Ops** when explicit diagnostics, import, training or refresh are needed.
3. Browse, filter and inspect existing lessons.
4. Create or edit approved lessons through **Editor**.
5. Review exact and near duplicates through **Duplicates**.
6. Ingest raw notes through **TritaLeLe**, keeping preview, staging, review and
   approval as separate actions.
7. Use **Vault**, **Stats** and **Timeline** to inspect the resulting knowledge
   base.
8. Use **Settings** to inspect effective local paths, storage roles and bounded
   support diagnostics; use **About** for product identity, license and support
   links.

## GUI views

| View | Purpose |
|---|---|
| Dashboard | Inspect workspace readiness, bounded summaries and next useful actions |
| Browse | Search, filter and export lessons |
| Detail | Read one lesson and inspect explained similarity |
| Editor | Create or update canonical Markdown lessons |
| Timeline | Inspect lessons by month, year or topic |
| Stats | Inspect counts, topics, tags and averages |
| TritaLeLe | Preview, stage, review and explicitly approve candidates |
| Vault | Inspect the canonical Markdown tree and trigger projection import |
| Duplicates | Review duplicate and near-duplicate pairs without mutation |
| Ops | Inspect health, run Vault Doctor, import, train and refresh |
| Settings | Inspect effective runtime paths, their semantic roles and explicit support diagnostics |
| About | Inspect product identity, version, license, local-first statement and support links |

## Dashboard and first-run states

`/app/` opens the Dashboard. Browse remains available at `#/browse`.

The Dashboard reads bounded workspace state only. It can distinguish a fresh
setup with no vault, an empty vault, a partially ready workspace, a ready
workspace and recoverable loading errors. It does not run duplicate review,
Vault Doctor, import, refresh or model training automatically.

The Markdown vault remains authoritative. Dataset projections, caches and
topic-model artifacts are derived and rebuildable.

## Settings, About and support diagnostics

**Settings** is read-only. It reports the effective Markdown vault, application
data directory, lesson projection, TritaLeLe candidate staging, cache directory
and topic-model path. Each location is classified as authoritative user data,
persistent application state, derived/rebuildable artifact or cache/temporary
state.

When reliable, Settings also identifies whether a path comes from a supported
directory-level override, a deprecated compatibility override, a platform
default or the product default. It does not expose unrelated environment
variables and loading the page does not create directories or mutate the vault,
projection, candidates, cache or model.

Each displayed path can be copied. Folder-opening actions are intentionally not
offered where the browser-hosted local GUI has no safe portable filesystem
bridge.

The **Support diagnostics** section is explicit: no diagnostic payload is
generated on page load. **Generate preview** requests a bounded JSON report
containing product/runtime metadata, effective path roles and coarse existence
status only. It excludes lesson and candidate contents, secrets, credentials,
tokens, cookies, authorization headers, arbitrary environment variables,
unrelated filesystem data and broad process/system inventories.

The complete JSON is shown before export. **Save diagnostic JSON** writes
exactly that preview without regenerating it.

**About** uses the same authoritative application version as the product shell.
It provides GiadaWare attribution, the MIT license and packaged full-license
reference, repository, issue tracker, releases, changelog and documentation
links, plus the local-first statement. LeLe Manager itself introduces no
account, telemetry, cloud storage or remote knowledge service.

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
