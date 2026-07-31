# ADR 0001: storage backend for LeLe Manager

> Language policy: ADRs are English-only canonical technical records.
> See the [documentation policy](../documentation-policy.md).

- **Status:** Proposed
- **Date:** 2026-07-13
- **Issue:** [#91 — Compare storage backends](https://github.com/gcomneno/lele-manager/issues/91)
- **Epic:** [#82 — TritaLeLe Knowledge Ingestion Pipeline](https://github.com/gcomneno/lele-manager/issues/82)

## Context

LeLe Manager is a personal local-first application. The repository often
describes its flow as `Markdown vault -> JSONL -> ML -> API`, but the current
code does not apply one authoritative source consistently:

- `src/lele_manager/cli/import_from_dir.py::import_from_dir` reads Markdown,
  uses the frontmatter `id` or derives it from the path, normalizes metadata
  and body, and produces records that also include `path`, `frontmatter`, and
  `frontmatter_hash`;
- `src/lele_manager/core/vault.py::write_lesson_markdown` writes body and
  frontmatter to the vault, while `import_vault_to_jsonl` rebuilds JSONL from
  the vault;
- `src/lele_manager/api/server.py::create_vault_lesson` and `update_lesson`
  write Markdown first and then reimport the vault, making the vault the
  authoring source in the current GUI flow;
- the same API still uses `load_lessons_df` to read JSONL directly and
  `append_lesson_to_jsonl` for `POST /lessons`, which does not write to the
  vault;
- the historical `add_lesson.py` and `list_lessons.py` CLIs use
  `src/lele_manager/core/storage.py`, which appends and scans JSONL directly;
- the main `lele` CLI and the GUI use the API instead;
- training and similarity accept `pandas.DataFrame` values:
  `train_topic_model.py` and `suggest_similar.py` read JSONL, while API
  training and similarity load the same dataset into a DataFrame;
- `models/topic_model.joblib` is a derived artifact;
- `scripts/lele-api-refresh.sh` makes the complete rebuild explicit:
  `vault -> data/lessons.jsonl -> models/topic_model.joblib`;
- vault tests verify Markdown write-back and reimport, while historical storage
  tests preserve direct JSONL behavior;
- default dataset and model paths are XDG-based, and `.gitignore` excludes
  local data, databases, and models from this repository.

Therefore, the vault is the intended source for the complete authoring flow,
but JSONL is still operationally mutable and may contain records absent from
the vault. This ambiguity must be resolved before adding more ingestion paths.

This ADR defines the target state. It does not itself change runtime behavior
or implement the following abstraction and migration work.

### Architectural layers

| Layer | Current state | Decided target |
|---|---|---|
| Markdown vault | GUI authoring and write-back; dataset rebuild | Authoritative source for approved lessons |
| Application storage | JSONL read or written directly by several components | Local, rebuildable, queryable SQLite projection |
| JSONL | Dataset, mutable storage, ML input, and fixtures | Derived snapshot for export, interoperability, fixtures, and ML |
| API / CLI / GUI | Mixed access through API or direct JSONL | Access lessons through application and storage boundaries |
| Topic and similarity | DataFrame from JSONL plus `joblib` model | Derived artifacts tied to an identifiable storage snapshot |
| Export and integrations | Markdown from API results; implicit JSONL | Explicit operations separated from the backend |

## Requirements and decision criteria

The selected architecture must:

1. remain simple to install and operate for a local Python application;
2. preserve portability, inspectability, and manual recovery;
3. support upsert, deletion, and complete replacement without unsafe rewrites;
4. provide transactions, constraints, queries, filters, and indexes;
5. support realistic concurrent reads and occasional writes for a local
   FastAPI/GUI application;
6. define an explicit schema and migration strategy;
7. allow full-text search without making it a portability prerequisite;
8. work for small datasets and moderate growth;
9. integrate with Python, Pandas, and scikit-learn;
10. support coherent backups, export, and isolated tests;
11. avoid an external service without a concrete requirement;
12. minimize migration cost from current code and data;
13. preserve Markdown and JSONL as interoperable formats without confusing
    either with the application database;
14. prepare the boundaries required by issues
    [#92](https://github.com/gcomneno/lele-manager/issues/92),
    [#93](https://github.com/gcomneno/lele-manager/issues/93), and
    [#94](https://github.com/gcomneno/lele-manager/issues/94).

## Options considered

### JSONL

JSONL has the lowest conceptual and operational cost. It is UTF-8, readable by
common tools, line-diffable, and already consumed by Pandas and project scripts.
It is appropriate for export, fixtures, exchange, and training snapshots.

As mutable storage, append does not guarantee ID uniqueness, while upsert and
delete require reading and rewriting the file. The current code demonstrates
both patterns: `core.storage.append_lesson` appends, while
`core.vault.upsert_jsonl_lesson` and `import_vault_to_jsonl` rewrite. JSONL
does not provide multi-record transactions, schema constraints, or indexes.
Reads and filters require scanning and materialization. Locking, atomic writes,
and recovery must be implemented by the application. Theoretical Git
friendliness does not change the fact that local data is excluded from this
repository.

**Assessment:** retain JSONL as a derived format, not the primary mutable
application backend.

### SQLite

SQLite is embedded and serverless, normally storing a database in one file.
Python exposes `sqlite3` in the standard library, although the module depends
on the SQLite library and is optional for distributors of custom CPython
builds. Supported platforms must verify it, but ordinary packaging does not
require another Python dependency.

SQLite provides transactions, constraints, SQL queries, indexes, efficient
updates and deletes, and schema-versioned migrations. It fits one local
application with many reads and occasional writes. WAL mode permits concurrent
readers and a writer, but only one writer at a time remains realistic. The
application must handle timeout and `SQLITE_BUSY`. WAL is unsuitable for
network filesystems, and `-wal` and `-shm` files are relevant when copying
state.

FTS5 provides indexed full-text search when compiled into SQLite. Supported
builds must detect and test it; baseline search must work without FTS5.
Coherent backups can use the Backup API or `VACUUM INTO`. Blindly copying only
the main database file during an active WAL session is not a backup strategy.

Pandas integration can occur by converting query results or records into a
DataFrame at the ML boundary. The database must not be versioned in Git; the
vault and textual exports remain the versionable and recoverable formats.

**Assessment:** best match for LeLe Manager's local CRUD and search workload.

### DuckDB

DuckDB is embedded, transactional, and optimized for columnar analytical
workloads and bulk operations. Its Python client can query Pandas DataFrames,
Arrow, and other formats directly, making it attractive for exploratory
analysis, statistics, and dataset preparation.

It is not a current `pyproject.toml` dependency. Ordinary embedded read-write
usage is centered on one process with concurrent writers inside that process.
Multi-process writing through remote Quack remains beta, while DuckLake with a
PostgreSQL catalog introduces external infrastructure. These modes add
operational cost without serving the simple local CRUD requirement better than
SQLite. Many small transactions are also not DuckDB's primary workload, and
its columnar advantages are limited for the current personal dataset.

**Assessment:** not the primary CRUD backend; a future analytical layer over
JSONL, Parquet, or SQLite remains possible when justified.

### Embedded or local document-oriented storage

This category includes in-process libraries such as TinyDB and similar
embedded products. TinyDB persists Python documents in JSON and offers a query
API. Flexible frontmatter maps naturally to documents, and debugging can
remain simple.

Transactions, concurrency, indexes, full-text search, and migrations vary by
product. A JSON-file solution repeats JSONL rewrite and locking problems. A
more capable solution adds a product-specific dependency and ecosystem.
Lessons already have stable, useful fields and relationships: unique ID, tags,
provenance, and synchronization generation. Schemaless flexibility does not
outweigh the mature consistency and query capabilities of SQLite. Future
fields can use migrations and, when useful, a JSON column for metadata not yet
promoted into first-class columns.

**Assessment:** rejected for the primary backend; no concrete advantage
outweighs SQLite.

### External document-store server

MongoDB or an equivalent provides flexible documents, queries, indexes,
concurrency, and transactions in suitable deployments. It also requires a
separate process or service to install, configure, secure, update, and back up.
Some guarantees depend on deployment topology.

LeLe Manager is personal, local, and distributable as a Python application.
There is no replication, sharding, remote multi-user access, or volume
requirement that justifies this operational cost.

**Assessment:** rejected. Reconsider only if real distributed requirements
emerge.

## Comparison matrix

Legend: `++` strongly favorable, `+` favorable, `0` mixed or neutral,
`-` unfavorable, `--` strongly unfavorable. These are project-specific design
assessments, not universal benchmarks.

| Criterion | JSONL | SQLite | DuckDB | Embedded document store | Server document store |
|---|---:|---:|---:|---:|---:|
| Local-first operational simplicity | ++ | ++ | + | + | -- |
| Python/runtime dependencies | ++ | ++* | - | - | -- |
| Data portability | ++ | + | + | 0 | 0 |
| Manual reading and debugging | ++ | + (CLI/tool) | 0 (tool) | +/0 | 0 |
| Transactions and consistency | -- | ++ | ++ | variable | ++ |
| Update and delete | -- | ++ | + | + | ++ |
| Queries, filters, and indexes | -- | ++ | ++ | +/0 | ++ |
| Interactive CRUD | - | ++ | 0/- | +/0 | ++ |
| Concurrency for a local app | -- | + | 0/- | variable | ++ |
| Schema, constraints, and migrations | -- | ++ | + | 0/- | + |
| Full-text search | -- | +* | -/0 | variable | + |
| Small datasets | ++ | ++ | + | + | - |
| Moderate growth | - | ++ | ++ analytical | 0/+ | ++ |
| Pandas / scikit-learn | ++ | + | ++ | 0/+ | + |
| Coherent backup | 0 | ++ | + | variable | + with operations |
| Git diff/versioning | ++ | -- | -- | +/-- by format | -- |
| Isolated and in-memory tests | + | ++ | ++ | + | -- |
| Desktop/local packaging | ++ | ++* | 0/- | 0/- | -- |
| Tool interoperability | ++ | ++ | ++ | 0/+ | + |
| Current migration cost | ++ | + | 0/- | 0/- | -- |

`*` Supported Python and SQLite builds must verify `sqlite3`, and especially
FTS5, explicitly.

## Decision

1. **Source of truth and identity:** the Markdown vault becomes the
   authoritative source for approved lessons. Authoritative content lives in
   the Markdown body and metadata in frontmatter. The canonical convention
   binds identity to location: `topic` equals the first relative directory and
   `id` equals the relative path without `.md`. Renaming or moving a file
   therefore requires updating `id`; changing the topic directory also
   requires updating `topic`. Under this convention, a move or rename is an
   identity migration and may invalidate external references.

2. **Application backend:** SQLite becomes the local indexed and queryable
   storage. It is a rebuildable projection of the vault, not an independent
   second source of truth.

3. **JSONL role:** JSONL remains a derived snapshot for export,
   interoperability, fixtures, and reproducible training or analysis input.
   During migration it may remain a compatibility backend behind issue #92's
   abstraction, but it is not the final backend or the canonical editing
   surface.

4. **DuckDB role:** DuckDB has no primary CRUD role. It may be reconsidered as
   a secondary analytical tool when volume or columnar queries justify it,
   operating over exports or snapshots.

5. **Document-oriented storage:** both embedded and server document stores are
   rejected. The embedded category does not provide enough advantage over
   SQLite for consistency and queries; the server category adds
   disproportionate operations without a distributed requirement.

6. **Services and issue #92 boundary:** user-facing create, update, and delete
   operations pass through an authoring service that validates and writes the
   vault. A synchronization service reads the vault and updates a queryable
   projection store. `upsert`, `delete`, and `replace-all` are internal sync
   capabilities, not business-logic or endpoint operations that modify SQLite
   directly. Separate export services read a projection snapshot and publish
   JSONL or other formats. Issue #92's abstraction represents the minimum
   projection contract without exposing JSONL, SQLite, SQL, Pandas, or the
   filesystem.

7. **Projection state:** each projection records the vault generation or
   fingerprint from which it was built. A mismatch must be detectable and
   exposed. API and CLI consumers must not silently report a stale projection
   as current. The concrete policy may require synchronization, return an
   explicit error, or operate in a clearly signaled degraded mode.

This is a target-state decision. Issue #92 must initially preserve the JSONL
behavior required by its own scope. The default changes to SQLite only after
verified parity and reconciliation of JSONL-only data.

## Rationale

SQLite addresses limitations already visible in the code: duplicate-prone
append, whole-file rewrites for upsert, scans for each filter, and the absence
of transactions. It does so with an embedded component compatible with the
local workload and packaging, without requiring a service.

Keeping Markdown authoritative preserves the authoring experience,
readability, portability, and independent Git history of the vault. Keeping
JSONL as a snapshot preserves working Pandas, scikit-learn, and external-tool
integration without forcing JSONL to act as a mutable database.

The separation also removes a false choice. Markdown, SQLite, and JSONL serve
different roles: authoritative content, application index/storage, and
exchange or derived dataset.

## Positive consequences

- Unique IDs, constraints, updates, deletes, and rebuilds can be atomic in the
  application storage.
- API, CLI, and GUI can share queries and ordering without always loading the
  complete dataset.
- Ordinary indexes and optional FTS5 support more efficient search and filters.
- SQLite is easy to create in a temporary file or in memory for tests.
- The vault remains readable, editor-friendly, and independently versionable.
- JSONL remains easy to export, inspect, and load into Pandas.
- The database can be rebuilt from the vault after corruption or schema change.
- The storage boundary keeps the backend replaceable without exposing it to
  external consumers.

## Negative consequences and trade-offs

- SQLite schema migrations and a schema version must be maintained.
- SQLite files are not suitable for Git diff or merge and must not be treated
  as vault backups.
- A filesystem commit and SQLite transaction cannot form one ACID transaction;
  synchronization needs an explicit protocol.
- WAL, timeouts, checkpoints, and `SQLITE_BUSY` handling require operational
  decisions and tests; one writer remains the realistic limit.
- FTS5 cannot be assumed everywhere; feature detection and fallback are
  required.
- DataFrame conversion becomes an explicit adapter instead of a direct
  `pd.read_json`.
- Two backends coexist during migration, temporarily increasing test surface.
- JSONL-only records must be identified and reconciled before the vault becomes
  the sole operational authority.

## Adoption plan

This plan belongs to later issues. Issue #91 does not implement it.

1. In #92, introduce the storage boundary and a JSONL adapter that preserves
   current behavior.
2. Introduce the authoring service as the only user-facing entry point for
   create, update, and delete of approved lessons; it validates and writes the
   Markdown vault.
3. Introduce a separate synchronization service that publishes projection
   snapshots and records their generation or fingerprint. Remove knowledge of
   JSONL paths, `pd.read_json`, and append/rewrite behavior from business rules
   without changing the default backend yet.
4. Add a SQLite adapter behind the same boundary with explicit schema version
   and migrations. Its incremental and transactional capabilities remain
   internal to synchronization.
5. Perform a read-only inventory of vault and JSONL. Report duplicates,
   JSONL-only records, missing IDs, and conflicts. Do not modify Markdown
   automatically.
6. Import the vault into a new SQLite database and compare counts, IDs, fields,
   hashes, and query results against JSONL.
7. Only after reconciliation, move API and CLI reads gradually to SQLite. GUI
   and the main CLI remain API consumers, and writes still pass through vault
   authoring.
8. Separate export services and publish JSONL atomically from the same
   projection snapshot for pipelines not yet migrated.
9. Move training and similarity to a snapshot or DataFrame obtained through
   the application boundary, recording its fingerprint or generation.
10. Remove direct JSONL access only after parity tests, stabilization, and a
    documented compatibility window.

## Compatibility and migration

### Data model

- **Vault:** approved `id`, topic, source, importance, tags, date, title, and
  provenance in frontmatter; content in the Markdown body. `topic` equals the
  first relative directory and `id` equals the complete relative path without
  `.md`. Rename, move, or topic-directory changes require coherent canonical
  metadata updates. Unknown frontmatter metadata must survive round trips.
- **SQLite:** queryable copies of IDs, metadata, and bodies, plus
  synchronization information such as relative path, content/frontmatter
  hashes, and generation. Exact tables and tag representation are deferred to
  #92.
- **JSONL:** complete documented representation of one generation, not an
  append-only log and not authority. Ordering must be deterministic for
  reproducible tests and diffs.
- **ML models:** rebuildable derived artifacts associated with the dataset
  fingerprint or generation used to train them.

### Updates, deletions, and consistency

User-facing changes to approved lessons pass through the vault authoring
service. The projection store is not an authoring interface.

Conceptually:

1. validate the complete lesson;
2. write or replace Markdown atomically;
3. let synchronization detect the new vault generation;
4. apply an internal upsert/delete or whole replacement to the projection
   store; SQLite synchronization may use a transaction;
5. publish the new projection generation only after synchronization completes;
6. invalidate or regenerate JSONL, statistics, and derived models.

An approved deletion removes the Markdown file, while Git may retain history.
The next synchronization removes the projection entry. If Markdown writing
succeeds but synchronization fails, the previous projection may remain
physically readable, but its generation no longer matches the vault. That
mismatch is stale state and must be exposed. The vault wins, synchronization is
repeatable, and the application does not attempt a destructive rollback of
already confirmed Markdown.

For a complete rebuild, all Markdown files are parsed and validated before
opening the transaction that replaces the dataset. Errors or duplicate IDs
prevent publication. JSONL export uses a temporary file and atomic rename,
never line-by-line in-place updates.

Permanent dual writes to Markdown and database without this authority rule are
not allowed. In particular, an endpoint must not update SQLite and then
"attempt" to write the vault while leaving the winning copy ambiguous.

### Rollback

- Until SQLite is default, JSONL remains selectable and compatibility tests
  preserve the previous behavior.
- After cutover, an application rollback regenerates JSONL from the vault and
  may use it temporarily as the projection. User-facing writes still pass
  through vault authoring; rollback does not restore authoritative direct
  JSONL writes or promote a SQLite copy newer than the vault.
- Each SQLite migration operates on a coherent backup or a rebuildable
  database and may fail without modifying the vault.
- No migration phase automatically rewrites frontmatter or body. Audit findings
  require explicit review.

### Test strategy

- contract suite for common JSONL/SQLite behavior: get by ID, deterministic
  list/search, coherent snapshot read, atomic whole-snapshot publication,
  counts, and generation/fingerprint;
- SQLite-specific tests for synchronization transactions and incremental
  updates, without extending those promises to JSONL;
- golden datasets with complete records, optional fields, Unicode, tags, and
  canonical IDs containing `/`;
- canonical checks that `id` equals the relative path without `.md` and
  `topic` equals the first directory;
- rename and move tests as identity migrations, including invalidated
  references to old IDs;
- filter, ordering, and serialization parity with current endpoints;
- rollback tests for invalid import, duplicates, interrupted transactions, and
  failed migrations;
- realistic concurrency tests with multiple readers, one writer, timeout, and
  limited retries;
- FTS5 feature tests in supported packaging and fallback tests without FTS5;
- fingerprint comparison across vault, SQLite, JSONL export, and model input;
- API, CLI, and GUI smoke tests without direct backend-format access.

## Conceptual boundary for issue #92

The port offers capabilities without fixing final Python signatures:

- get one lesson by ID;
- deterministic filtered list and search with limits;
- read one coherent snapshot;
- atomically publish or replace a complete snapshot;
- obtain essential counts and statistics without duplicate scans;
- expose a generation or fingerprint useful for cache and derivatives.

The SQLite adapter may additionally provide synchronization with internal or
optional upsert, delete, and transaction capabilities. These are not part of
the common minimum and do not force JSONL to simulate general transactions or
ACID semantics.

The port excludes:

- Markdown parsing and rendering;
- vault scanning and write-back;
- user-facing create, update, and delete;
- JSONL, Markdown, or other import/export;
- DataFrame construction;
- model training, serialization, and cache;
- SQL details, database paths, and Pandas-specific types.

Authoring is a separate application service that validates user-facing
operations and writes the vault. Synchronization reads the already
authoritative vault, validates canonical ID/topic conventions, and publishes a
new projection through `replace-all` or adapter-specific incremental
operations. SQLite transactions are an implementation detail of that sync.
Export is another service that reads a snapshot through the port and
serializes JSONL or other formats.

## Impact on later issues

### #92 — Introduce storage abstraction layer

Issue #92 implements the minimum port and the JSONL compatibility adapter while
preserving external behavior and current JSONL semantics, including temporary
legacy write flows. It isolates access currently spread across `core.storage`,
`core.vault`, and `api.server`, and introduces conceptual boundaries among
authoring, synchronization, projection store, and export.

It does not need to force the final cutover of user-facing writes to the vault
in the same issue. Vault-only authoring follows after reconciliation and parity
tests. In the target state, endpoints and business logic do not call projection
mutations directly; SQLite upsert/delete and transactions belong to sync.
Import/export does not belong inside the repository abstraction.

### #93 — Expose lessons for external quiz and review tools

Issue #93 may depend on a stable application lesson/snapshot contract: get by
ID, deterministic list/search, metadata, body, and generation.

Contract stability does not mean an ID survives a move. Because canonical ID is
derived from the path, rename and move are identity migrations and may
invalidate external references. Consumers must not assume ID permanence across
those operations. A future alias strategy or immutable external key may be
considered separately.

External consumers receive no SQLite paths, SQL rows, DataFrames, or promises
about internal JSONL representation. A versioned JSONL export or paginated API
may transport the same contract. Quiz tools remain read-only consumers and do
not become another authority.

### #94 — TritaLeLe

TritaLeLe introduces raw sources, provenance, chunking, candidates, and human
review. Candidates are not approved lessons and must not enter the
authoritative vault or ML dataset directly.

The workflow keeps separate staging. Only explicit human approval produces
Markdown with canonical ID and provenance, followed by synchronization to the
projection and regeneration of derived artifacts. A distinct candidate port
may be introduced without overloading the approved-lesson repository.

This separation makes the flow deterministic:

```text
source material
  -> candidate
  -> approval
  -> vault
  -> storage
  -> export / ML
```

It prevents unreviewed text from changing search, topic, or similarity results.

## Deferred alternatives

- Mandatory FTS5: deferred until packaging and tokenizer behavior are verified;
  SQLite remains selected with fallback search.
- DuckDB as an analytical layer or Parquet export: deferred until a workload
  demonstrates value.
- Fully normalized metadata versus a JSON column for extensions: deferred to
  #92's schema decision, provided IDs and queried fields receive explicit
  constraints and indexes.
- Change log, event sourcing, or permanent tombstones: not currently required;
  vault Git history and synchronization generations cover initial recovery.
- Multi-user database server: deferred until remote access, replication, or
  multiple-writer requirements exist.

## Conditions for reconsidering the decision

Reconsider this ADR if at least one condition becomes true:

- LeLe Manager becomes multi-user or needs distributed or remote writers;
- Markdown can no longer represent approved content or provenance without loss;
- measured volume and query workloads make indexed SQLite inadequate;
- columnar scans or Parquet become the dominant workload, making DuckDB a
  primary candidate;
- relevant packaging targets cannot provide `sqlite3` reliably and bundling it
  is unacceptable;
- filesystem/database synchronization remains operationally unreliable despite
  generations, atomic rebuilds, and stale-state detection;
- heterogeneous document requirements cannot be met by SQLite schema plus JSON
  extension fields.

## Risks and open questions

- Which real records exist only in JSONL, and how are they promoted to the
  vault without losing `created_at` or other fields?
- Is deletion represented by a Git-versioned physical removal or an explicit
  tombstone?
- Which #94 provenance fields become queryable columns, and which remain
  frontmatter extensions?
- Which Python builds and operating systems belong to the `sqlite3` and FTS5
  packaging matrix?
- Is the API process the only SQLite writer, or must separate CLI processes be
  coordinated?
- Which vault change-detection strategy fits real usage: explicit refresh,
  watcher, or startup scan?
- What user experience accompanies an identity migration caused by rename or
  move?
- What concrete policy applies when projection generation differs from the
  vault fingerprint: mandatory sync, explicit error, or signaled degraded
  mode?
- Will aliases or an immutable external key eventually be needed for durable
  references? The current convention remains `id = relative path without .md`;
  this ADR does not define an alias schema.

## References

### Repository and planning

- [Issue #82 — Epic: TritaLeLe Knowledge Ingestion Pipeline](https://github.com/gcomneno/lele-manager/issues/82)
- [Issue #91 — Compare storage backends](https://github.com/gcomneno/lele-manager/issues/91)
- [Issue #92 — Introduce storage abstraction layer](https://github.com/gcomneno/lele-manager/issues/92)
- [Issue #93 — Expose lessons for external quiz and review tools](https://github.com/gcomneno/lele-manager/issues/93)
- [Issue #94 — Add raw knowledge ingestion workflow (TritaLeLe)](https://github.com/gcomneno/lele-manager/issues/94)
- `README.md`, sections about LeLe Vault, ML, API, and GUI
- `ROADMAP.md`, sections about the vault/JSONL/ML/API flow and current state
- `src/lele_manager/cli/import_from_dir.py::{LeLeRecord,import_from_dir}`
- `src/lele_manager/core/vault.py::{write_lesson_markdown,import_vault_to_jsonl,upsert_jsonl_lesson}`
- `src/lele_manager/core/storage.py::{append_lesson,load_lessons,iter_lessons}`
- `src/lele_manager/api/server.py::{load_lessons_df,append_lesson_to_jsonl,create_vault_lesson,update_lesson,ops_refresh,train_topic}`
- `src/lele_manager/cli/{add_lesson,list_lessons,lele,train_topic_model,suggest_similar}.py`
- `src/lele_manager/ml/{features,topic_model,similarity,similarity_service,similarity_backend}.py`
- `frontend/src/lib/api.ts`
- `scripts/{lele-api-refresh.sh,e2e-prepare.py}`
- `tests/{test_lessons_storage.py,test_add_lesson_cli.py,test_api_vault.py,test_import_from_dir.py,test_api_basic.py,test_search_api.py,test_train_topic_model_cli.py,test_similarity_service_equivalence.py}`

### Official technical documentation

- [Python `sqlite3` — DB-API 2.0 interface for SQLite databases](https://docs.python.org/3/library/sqlite3.html)
- [SQLite — FTS5 Extension](https://www.sqlite.org/fts5.html)
- [SQLite — Write-Ahead Logging](https://www.sqlite.org/wal.html)
- [SQLite — Online Backup API](https://www.sqlite.org/backup.html)
- [DuckDB — Concurrency](https://duckdb.org/docs/stable/connect/concurrency)
- [DuckDB — Python API overview](https://duckdb.org/docs/stable/clients/python/overview)
- [DuckDB — Transaction management](https://duckdb.org/docs/stable/sql/statements/transactions)
- [TinyDB documentation](https://tinydb.readthedocs.io/en/latest/)
- [MongoDB — Self-managed deployments](https://www.mongodb.com/docs/manual/self-managed-deployments/)
- [MongoDB — Production notes for self-managed deployments](https://www.mongodb.com/docs/manual/administration/production-notes/)
