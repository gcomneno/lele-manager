# ADR 0008: Per-LeLe canonical revision history and rollback

## Decision

LeLe Manager maintains an inspectable revision history for canonical LeLe
without changing the source-of-truth hierarchy.

The current approved LeLe remains the Markdown file in the registered Vault.
Revision history is durable editorial state, not canonical knowledge and not a
rebuildable projection.

For each registered Vault, revision state is stored under its existing
application-data scope:

```text
<data-root>/vaults/<vault-id>/lesson-revisions.json
```

It is therefore isolated by immutable Vault UUID and is separate from:

- canonical Markdown in the Vault filesystem;
- `lessons.jsonl` projection state;
- TritaLeLe candidate/review history;
- duplicate-review decisions;
- ML/model/cache artifacts.

The history document uses an explicit versioned schema, validated reads,
same-process serialization and atomic replacement. Malformed, unsupported or
unsafe history state fails closed for history-dependent mutation.

## Revision identity and canonical fingerprint

A revision has two deliberately different identifiers.

`revision` is a zero-based, monotonically increasing integer scoped to one
stable lesson ID. It identifies a historical revision boundary.

`canonical_fingerprint` is:

```text
sha256:<hex digest of the exact canonical Markdown bytes>
```

It identifies exact canonical state and is the optimistic-concurrency token.

These concepts must not be collapsed. A rollback can restore byte-for-byte
content from an earlier revision, so two distinct revision boundaries may have
the same canonical fingerprint while retaining different revision numbers,
timestamps and actions.

Semantic fingerprints used by duplicate detection are not suitable for this
contract because they intentionally normalize presentation differences.

## Revision contents

Each persisted revision records enough information to inspect and restore the
canonical state:

- stable lesson ID;
- monotonically increasing revision number;
- exact canonical fingerprint;
- UTC timestamp;
- action describing the boundary (`baseline`, `edit`, or `rollback`);
- optional human-readable reason;
- canonical relative path observed for that revision;
- complete UTF-8 canonical Markdown snapshot;
- for rollback revisions, the historical revision selected as the restore
  source.

Complete snapshots are preferred over delta-only storage. Diffs are derived at
read time from two revision snapshots and never become an authority-bearing
log.

The maintained Markdown size/security limits remain applicable. Revision
history must not introduce an unbounded single-record write path.

## First maintained edit

Existing Vaults require no migration rewrite.

When a canonical lesson without maintained history is first changed through
the revision-aware authoring boundary, its existing canonical Markdown becomes
revision `0` (`baseline`). The successful resulting canonical state becomes
revision `1`.

Subsequent successful mutations append exactly one new revision boundary.

An identical/no-op write does not manufacture a new canonical revision merely
because an update endpoint was invoked.

## Optimistic concurrency

Revision-aware update and rollback require the caller to provide the
`expected_revision` canonical fingerprint loaded with the current lesson.

Inside `canonical_mutation_boundary()` the application re-resolves exactly one
canonical lesson and recomputes its exact fingerprint immediately before the
mutation.

If the current fingerprint differs, the operation fails with a stale-revision
conflict. It must not silently reload and retry against newer canonical state.

External filesystem edits are therefore detected even when they bypass LeLe
Manager history.

The revision number is historical identity; the exact canonical fingerprint is
the mutation precondition.

## Mutation and history consistency

History recording and canonical Markdown mutation form one maintained
application operation, but LeLe Manager does not claim cross-filesystem ACID
transactionality.

Before mutation the application captures the exact current canonical bytes,
validates the current history state, and checks the caller's exact-byte
precondition.

The operation uses the existing canonical mutation exclusion boundary. Revision
history itself is persisted with same-directory atomic replacement. Rollback and
its bounded canonical recovery also use atomic replacement of the existing
canonical file. Ordinary canonical edit currently uses the established
`write_lesson_markdown()` primitive and therefore does not claim an atomic file
replacement for that individual Markdown write.

For the first maintained edit, the baseline revision can be durably established
before the changed canonical Markdown is written. If that canonical write then
fails, the original Markdown remains unchanged and the baseline remains a
truthful snapshot of that unchanged canonical state.

If history persistence fails after a canonical write, the application performs
the bounded recovery required by the maintained contract and reports whether
canonical/history coherence was restored. It must not silently leave an
unexplained current canonical state outside the maintained timeline.

A crash between independent filesystem commits remains outside a claim of
filesystem-wide atomicity.

## Rollback

Rollback is an explicit new canonical mutation. It never removes, rewrites or
moves the historical timeline pointer backwards.

The caller supplies:

- the historical `target_revision`;
- the current `expected_revision` canonical fingerprint.

The target snapshot is loaded from the active Vault's revision store. The
current canonical fingerprint is revalidated inside the canonical mutation
boundary immediately before writing.

A successful rollback restores the selected historical canonical Markdown
bytes and appends a new revision whose action is `rollback`. That new revision
may have the same canonical fingerprint as an older revision while retaining a
new monotonic revision number and timestamp.

Rollback does not mutate a rebuildable projection directly.

## Derived reconciliation

After canonical edit or rollback success, the maintained derived reconciliation
runs against the resulting Vault.

Canonical success and derived refresh success remain separate outcomes.

If canonical Markdown and revision history commit successfully but projection
refresh fails:

- the canonical mutation remains successful;
- the new revision remains current and inspectable;
- the API reports partial success explicitly;
- the caller can retry derived reconciliation without repeating the canonical
  mutation.

A derived failure must never be reported as if the canonical rollback or edit
itself failed.

## Diff

Diff is a read operation over immutable historical snapshots.

The API may expose:

- metadata field changes;
- body changes;
- a readable unified Markdown diff.

No stored diff is required for reconstruction or rollback. The exact snapshots
and their fingerprints remain the evidence.

Comparisons involving malformed or missing maintained history fail explicitly
rather than substituting projection content.

## Integration with other mutations

This ADR establishes the maintained revision-history boundary for ordinary
canonical edit and rollback.

Other canonical mutation workflows, including lifecycle edits, duplicate
merge, deletion, transfer and bulk/destructive operations, must integrate with
revision history where their maintained contract requires recoverable
per-LeLe history.

They must not create an alternate revision mechanism.

Integration may be delivered incrementally when a workflow has additional
transactionality or identity semantics that require its own focused design.

## Snapshot relationship

Revision history is durable editorial state and therefore belongs conceptually
with other non-rebuildable per-Vault editorial data.

Portable Vault snapshot support must eventually preserve revision history so a
restored Vault does not silently lose its maintained editorial timeline.

That integration must preserve snapshot schema/versioning and validation rules;
it must not be added by silently changing snapshot schema version `1`.

## UI and localization

Detail and Editor expose the maintained history for the selected LeLe.

The UI must provide:

- current canonical revision/fingerprint state;
- revision timeline;
- explicit revision comparison;
- readable metadata/body differences;
- explicitly confirmed rollback;
- stale-update feedback;
- separate canonical-success/derived-refresh-failure feedback.

Maintained English and Italian UI/documentation remain synchronized.

## Non-goals

This decision does not:

- make revision history canonical knowledge;
- use Git history as the application history API;
- introduce cloud synchronization;
- provide collaborative multi-user locking;
- claim filesystem-wide ACID transactions;
- replace candidate review history;
- infer revisions from projection generations;
- automatically change lifecycle or other canonical metadata.
