# Projection store

LeLe Manager accesses its queryable lesson dataset through the typed port in
`lele_manager.core.projection_store`. The boundary is intentionally small and
backend-neutral:

- open one coherent, immutable snapshot;
- get a lesson by its canonical ID, including IDs containing `/`;
- list and search with portable filters, deterministic ordering and limits;
- obtain essential counts and a deterministic content generation from that
  same snapshot;
- validate and atomically publish a complete replacement snapshot.

Lesson records retain fields unknown to the current application. The port does
not expose JSONL, filesystem paths, Pandas objects, SQL, or backend-specific
transactions. Pandas conversion for ML and analytics remains an application
boundary, rather than part of the storage contract.

## Current compatibility backend

Backend composition occurs in `lele_manager.composition.projection_store`.
Production readers and whole-snapshot publishers request the neutral
`ProjectionStore` there; JSONL remains the default compatibility adapter.

`JsonlProjectionStore` is the default adapter during the migration described by
[ADR 0001](adr/0001-storage-backend.md). It reads existing UTF-8 JSONL files and
publishes canonical JSONL ordered by lesson ID. Object keys are sorted and
Unicode is emitted directly. Publication has stable bytes for equivalent
content. On reads, `LessonOrder.SNAPSHOT` exposes physical record order, so the
SHA-256 generation includes that order: different observable snapshot order
means a different generation. Blank lines are accepted for compatibility.

A read validates the complete file. Malformed JSON, non-object records, missing
or empty IDs, invalid UTF-8, and duplicate IDs are explicit errors; they are not
silently skipped. Each snapshot builds its ID lookup and essential statistics
in that single validation pass.

Whole-snapshot publication validates everything before touching the current
file, writes and fsyncs a temporary file in the destination directory, then
uses an atomic replace. A failure before replace leaves the previous snapshot
readable and removes the temporary file.

The historic `add_lesson` CLI and `POST /lessons` endpoint still append JSONL
records because removing that behavior is outside issue #92. This is exposed
only through the explicitly named `JsonlLegacyAppendFacade`, not through the
common projection port. It validates the complete existing snapshot and rejects
duplicate IDs before writing.

Writers are assumed to be serialized by the local application. There is no
cross-process transaction or locking: simultaneous whole-snapshot publishers
are last-writer-wins, while simultaneous legacy append writers are unsupported.
Vault rebuilds and directory imports use atomic whole-snapshot publication. No
SQLite cutover occurred: SQLite remains a future adapter and is neither
implemented nor selected by default here.
