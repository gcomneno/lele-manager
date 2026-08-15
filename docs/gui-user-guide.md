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
menu entry or desktop icon. The installer owns only
`${XDG_DATA_HOME:-~/.local/share}/lele-manager/install/`; the surrounding
`lele-manager` directory remains the persistent runtime-data namespace.

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
The language selector is in the always-reachable global header. The maintained
GUI languages are **English** and **Italiano**.

Changing language updates the GUI immediately without reloading the page. The
explicit choice is stored locally in the browser under
`lele-manager.locale`. Missing, malformed or unsupported stored values fall
back safely to English; browser-language auto-detection is intentionally not
used.

GUI localization affects product presentation only. It does not translate or
modify user-authored LeLe, Markdown vault content, dataset values, topic names,
source names, paths, IDs, API payloads or navigation identities.

## Application shell

The global header contains application-wide context and utilities: the current
workspace name, compact API/dataset/search-model status, language control,
**Search or commands**, and **Help**. It deliberately does not contain page
actions such as Save, Delete, model refresh, or a permanent creation CTA.
Version and full product identity remain authoritative in **About**.

Use the navigation button in the header to show or hide the complete sidebar.
This preference is stored locally as `lele-manager.sidebar-visible.v1` and is
independent from the collapsible **Knowledge**, **Capture**, and **Manage**
groups. Hiding the sidebar never removes the header controls; showing it again
preserves group disclosure and the current navigation item.

Use **Search or commands** or **Ctrl+K** to quickly open real destinations,
including Dashboard, Browse, Timeline, Statistics, Collection, Vault,
Duplicates, System, Diagnostics, About, and **New LeLe**. Search LeLe opens
Browse; it does not create a second search system. **New LeLe** remains under
**Capture** in navigation and is also available as an explicit command.

**Help** provides the user guide, Diagnostics, the maintained GitHub bug-report
form, About, and the command shortcut reminder. It neither generates nor sends
diagnostic data. On narrow screens the header stays available above recoverable
navigation and avoids horizontal overflow.

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
8. Use **Diagnostics** to inspect support status and prepare a bounded report;
   use **About** for product identity, license and project
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
| Diagnostics | Inspect support status, prepare an explicit bounded diagnostic package, and inspect runtime paths |
| About | Inspect product identity, version, license, local-first statement and support links |

## Dashboard and first-run states

`/app/` opens the Dashboard. Browse remains available at `#/browse`.

The Dashboard reads bounded workspace state only. It can distinguish a fresh
setup with no vault, an empty vault, a partially ready workspace, a ready
workspace and recoverable loading errors. It does not run duplicate review,
Vault Doctor, import, refresh or model training automatically.

The Markdown vault remains authoritative. Dataset projections, caches and
topic-model artifacts are derived and rebuildable.

## Diagnostics, About and support handoff

**Diagnostics** is read-only. It begins with API, dataset, search-model and
LeLe Manager version status. Generate a bounded report explicitly, inspect its
preview, then Copy JSON or Download JSON; both use the exact preview text.

**Request support** deliberately opens the maintained GitHub bug-report form.
It neither generates, uploads nor transmits diagnostic data. Review
`lele-manager-diagnostics-<version>.json` and decide whether to attach it.

**Technical details** is collapsed by default and retains effective runtime
paths, their semantic roles, existence, provenance and Copy path actions. The
diagnostic package excludes lesson/candidate contents, secrets, credentials,
tokens, cookies, authorization headers, arbitrary environment variables,
unrelated filesystem data and broad process/system inventories.

**About** uses the same authoritative application version as the product shell.
It provides GiadaWare attribution, the MIT license and packaged full-license
reference, repository, issue tracker, releases, changelog and documentation
links, plus the local-first statement. LeLe Manager itself introduces no
account, telemetry, cloud storage or remote knowledge service.

## Metadata authoring

Editor loads local, read-only suggestions for known topics, tags, and sources
from the current lesson projection. They are conveniences: you may write a new
topic, tag, or source, and suggestions never change metadata automatically.
Tags are added and removed as visible chips, while Importance is explicitly
bounded from 1 to 5. Similarity can offer a topic only after an explicit check;
applying it is a separate explicit action.

Lifecycle is also author-controlled. Every lesson is one of **Active**,
**Review needed**, **Deprecated**, or **Archived**; lessons without an explicit
canonical marker are Active. Editor exposes the lifecycle selector directly and
an optional **Superseded by** stable-ID field. Selecting Active deliberately
clears an older non-active marker, while clearing Superseded by deliberately
removes the canonical replacement reference. Saving remains the only action
that writes these changes to the canonical Markdown vault. Derived signals
never perform lifecycle transitions automatically.

## Managing an existing LeLe

Browse and lesson Detail expose the same actions for an existing LeLe:
**Modify**, **Inspect**, and **Delete**. Inspect opens the maintained explained
similarity surface; Editor keeps its explicit **Check similarity** action while
editing.

Browse, search, List all, and Markdown export are Active-only by default. Use
the Lifecycle selector to explicitly request Review needed, Deprecated,
Archived, or All states. Non-active lessons receive a distinct visual treatment
and lifecycle badge. The same lifecycle scope is applied to export.

Detail remains available by stable ID even for non-active lessons. When a lesson
has `superseded_by`, Detail links to the maintained replacement. The replacement
also exposes derived **Supersedes** links back to lessons that point to it, so
the relationship can be navigated in both directions where available.
Supersession itself never deletes, merges, rewrites, or changes the lifecycle of
either canonical lesson.

Delete always shows the lesson title (or *Untitled*) and stable ID for
confirmation before permanently removing that exact canonical Markdown file.

Browse also supports explicit multi-selection for the current loaded result
snapshot. **Select all visible** selects only the currently rendered, limit-bound
results; it never selects hidden, unloaded, or other vault/search matches. A new
Search or List all execution clears the selection, even where IDs overlap, so
you must select targets again. **Delete selected** shows every selected title
and stable ID before confirmation. It deletes those canonical Markdown sources,
then refreshes the derived projection once for the whole batch. Per-target
canonical failures and a final derived-refresh failure are reported separately;
canonical successes remain deleted. Inspect selection is intentionally deferred:
the maintained similarity APIs do not define an unambiguous selected-subset
contract. Duplicate-pair resolution remains a separate workflow.

After a normal delete, LeLe Manager automatically rebuilds the derived
projection and search state; you do not need to use **System → Update all**.
If the Markdown deletion succeeds but the derived refresh fails, the UI reports
that partial outcome accurately: the canonical lesson is gone, while search and
similarity may remain stale until a later refresh succeeds.

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

![Duplicate review](images/gui/duplicates.png)

### Resolve duplicate candidates deliberately

Duplicate detection is advisory: it never deletes, merges, or changes lesson
metadata automatically. Each pair keeps both canonical Markdown sources visible
and offers explicit actions. You can open either exact ID in the editor, keep
one and permanently delete the other after a confirmation that names both
lessons, mark the pair as **Not duplicates**, or open **Merge**.

**Not duplicates** is durable local application state, not Markdown metadata.
It hides the pair only while both lessons retain the same material content:
body text, title, topic, source, importance, tags, and date. A material change
makes a detected pair reviewable again. Decisions are currently scoped by the
resolved vault path; this intentionally isolated temporary scope will migrate
to registered vault identity in the future multi-vault work.

Merge is a human-controlled editing flow. Choose the existing left or right ID
that will survive, compare both read-only sources, manually edit the resulting
lesson, then explicitly confirm saving it and deleting the other source. LeLe
Manager never auto-concatenates or uses AI to synthesize a merge.

Markdown is canonical. A delete or merge writes canonical sources first and
refreshes the derived projection/search state afterward. If that refresh fails,
the screen reports the canonical truth separately and does not pretend that the
operation rolled back; refresh derived data from System when appropriate.

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

Use **Vault** to create a portable snapshot for an explicitly selected
registered Vault. **Create snapshot** downloads a versioned ZIP without
switching the active Vault. It includes canonical Markdown, that Vault's
candidate staging, and its duplicate-review decisions; it excludes the global
registry, JSONL projection, similarity cache and topic model.

To restore, choose a local ZIP and an explicitly registered target, then use
**Validate and preview restore**. The read-only preview identifies source
provenance and target UUID/path and lists additions, replacements, removals and
unchanged Markdown. The maintained Vault contract makes every `.md` file below
the Vault root canonical input (including one without frontmatter), so exact
restore removes any target Markdown absent from the snapshot. Unrelated
non-Markdown files are preserved. Type the actual target Vault name for the
second confirmation. Archives are versioned and fully validated before any
write: bounded ZIP sizes, safe relative paths, checksums, and no encrypted or
link-like members or unsafe source/target links.

The destination retains its own registry UUID, display name, path and active
status even for a snapshot made by another Vault. Its candidate and duplicate
state is restored only into that destination scope. On success LeLe Manager
rebuilds the projection, invalidates similarity data and removes an old topic
model. If derived refresh fails, the UI explicitly reports canonical success
and that derived data needs attention. A changed artifact, target Markdown,
candidates, duplicate decisions or selected target makes the preview stale and
requires a new preview. A failed canonical/editorial application attempts
bounded rollback and reports whether recovery succeeded; this is not a
filesystem-wide transaction.

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

## Vault management

The Vault screen manages registered local Vaults. **Create Vault** makes a new
empty directory; **Register existing Vault** adds an existing directory without
importing or changing Markdown. Activating a Vault refreshes its projection in
read-only mode and reloads the workspace. Rename changes only the display name.
**Remove from Manager** never deletes files on disk and cannot remove the active
Vault. On first run `LELE_VAULT_DIR` bootstraps the initial Vault; afterwards
the persisted registry is authoritative and changing that variable does not
switch Vault.
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

## Vault-to-Vault Merge, Copy, and Move

The Vault page supports explicit transfers between two different registered
Vaults. The visible direction is **Source Vault name → Destination Vault name**;
UUIDs and filesystem paths remain visible in the preview for inspection.

**Merge** and **Copy** are non-destructive defaults: only the checked approved
canonical lessons are considered and the source stays intact. **Move** is
destructive per lesson and is visibly separated from those operations.

Always validate and preview before execution. Preview can classify a lesson as
New, Identical, Already present, Same ID, Path conflict, or Likely duplicate.
Same-ID/path/duplicate conflicts are never overwritten automatically. Choose
**Keep destination** or **Skip**, then validate/preview again: changing a
resolution invalidates the old plan by design.

Execution is stateless and rejects a stale plan if source, destination,
operation, explicit selection, resolutions, registered context, or canonical
Markdown changed after preview. Changing the destination in the GUI also clears
the displayed preview, and late asynchronous preview responses are discarded.

Move is destination-first. LeLe Manager creates a new destination canonical
file without replacement, or proves that an existing lesson with the same
stable ID has byte-for-byte identical canonical Markdown. It reverifies those
exact destination bytes before deleting the corresponding source lesson. A
material/duplicate fingerprint alone is never sufficient for source deletion.
Destination failure leaves source untouched; source-delete failure leaves the
successful destination in place.

Canonical Markdown and derived state have separate outcomes. A canonical write
can succeed while destination projection/model/cache reconciliation fails. The
canonical success remains authoritative and is reported as partial success; for
Move, exact verified destination canonical success may still allow source
deletion because derived state is rebuildable. Destination derived state is not
rebuilt for exact/no-op or skipped items, and source derived state is rebuilt
only after an actual source deletion.

Transfers never copy candidate/editorial staging or duplicate-review decisions.
The hardened canonical filesystem boundary is shared with snapshot work from
#218. Future #194 is reserved for separately confirmed destructive whole-Vault
Danger Zone workflows; this transfer feature never deletes a Vault.

## System Danger Zone

System contains a visually separate **Danger zone** for destructive operations on one explicitly selected registered Vault. Every operation is preview-first: the preview shows the Vault display name, resolved path, approved-lesson count, affected scoped state, what will be deleted, what will remain, and the exact typed confirmation phrase. Changing the target, operation, relevant managed state, registry context, or merge destination makes the old plan stale.

- **Empty Vault** deletes approved canonical Markdown and then reconciles derived projection/search state. Registration, the Vault directory, candidate staging, and duplicate decisions remain.
- **Reset Vault completely** deletes canonical Markdown, candidate staging, Vault-scoped duplicate decisions, projection, and topic-model state, while preserving the registration and directory.
- **Delete Vault from disk** is allowed only for an inactive Vault. It refuses symlinks, special nodes, and non-Markdown regular files rather than deleting data LeLe Manager cannot prove it owns. After the managed directory is removed, scoped application state and the registry entry are removed separately and partial failures are reported.
- **Merge and delete source** is a separate destructive operation after #193. It is enabled only when every source lesson can be re-proved in the explicit destination with the same stable ID and byte-for-byte identical canonical Markdown. No session receipt or semantic fingerprint can authorize source deletion.

The optional **Create snapshot backup before continuing** reuses the maintained Vault snapshot format. If selected, the snapshot must be created and persisted successfully before the first destructive canonical mutation; backup failure blocks deletion. Snapshot backup covers managed canonical Markdown plus scoped candidate and duplicate-review state, not arbitrary foreign files.

Canonical and derived outcomes are reported independently. A partial canonical deletion triggers reconciliation to the actual remaining canonical state where possible; a derived cleanup failure never rewrites the reported canonical outcome. No danger-zone action switches the active Vault or targets another registered Vault implicitly.
