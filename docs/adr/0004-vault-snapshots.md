# ADR 0004: Portable per-Vault snapshots and exact restore

## Decision

LeLe Manager uses a versioned ZIP artifact for a snapshot of exactly one
registered Vault. Format `lele-vault-snapshot`, schema version `1`, contains a
deterministically ordered `manifest.json`, `canonical/<relative Markdown path>`
members, `editorial/candidates.json`, and
`editorial/duplicate-decisions.json`. The manifest records the creation time,
source UUID/name as provenance only, and SHA-256/size inventory for every
payload member. Archive paths are always relative POSIX paths; absolute source
paths are neither stored nor restore authority.

Canonical state is every regular `.md` file recursively below the registered
Vault root. This is the maintained Vault contract: the importer and Vault tree
both enumerate that complete namespace, including Markdown without
frontmatter. Candidate staging and the
UUID-scoped duplicate-review decisions are durable, non-rebuildable editorial
state and are included. The global Vault registry is application state and is
never included or replaced. Projection JSONL, in-memory similarity indexes, and
the topic-model cache are derived/rebuildable and are excluded.

## Restore contract

Restore selects an explicit registered destination UUID. Source provenance does
not have to match it: restoring A into B writes A's canonical/editorial payload
into B's scoped state while B retains its UUID, display name, filesystem path,
and active selection. No registry entry is created or changed. Candidate and
decision state is scoped to B; no other Vault scope is read as payload or
modified.

The operation is exact managed-state restore: archived Markdown replaces the
target Vault's managed Markdown and target Markdown absent from the archive is
removed. Thus an unrelated Markdown file cannot be preserved as an exception:
it is canonical input by the established Vault contract. Unrelated
non-Markdown files are never removed. A read-only preview
lists additions, replacements, removals, unchanged files, target identity/path,
editorial effects, and derived-state effects. Its stateless digest covers the
validated artifact, target UUID/path, and current target canonical/editorial
state. Execution recomputes it and returns a conflict if anything changed.

## Security and recovery

Archives are untrusted. Raw artifact bytes are limited to 300 MiB; member count
is limited to 10,000, each member to 32 MiB, and total declared and actually
read uncompressed payload to 256 MiB. Validation rejects invalid/truncated ZIPs, unsupported
schemas, missing or duplicate manifests/members, undeclared payload, duplicate
or case-colliding canonical paths, directory/file collisions,
unsafe/absolute/traversing/Windows-style paths, encrypted or non-regular
members, digest/size mismatches, bounded-size violations, and malformed
candidate or duplicate documents. Snapshotting preserves managed Markdown
bytes even when Vault Doctor would report editorial metadata defects; backup
does not repair or silently exclude canonical source.
All checks and temporary staging complete before canonical mutation. Snapshot
creation also refuses symlinked Vault entries and special filesystem nodes, so
it cannot archive external data through a link. Target Vault roots, existing
Markdown, and destination components reject symlink redirection; writes
recheck immediately around their mutation boundary and are constrained to the
selected registered root. This is a bounded best-effort TOCTOU defence, not a
claim of kernel-level race-free filesystem transactionality.

Apply is a bounded transaction: it records the complete original managed
Markdown and editorial scope, then attempts exact application. A mutation
failure triggers rollback and reports whether rollback succeeded; no
filesystem-wide atomicity is claimed. After canonical success the projection is
rebuilt, similarity cache invalidated, and old topic model removed. A derived
failure is reported as partial success: canonical restore remains true and
requires a later derived refresh.

Only schema version `1` is accepted. Future versions are rejected rather than
best-effort imported. This reusable domain capability is the backup boundary
that #194 can call before a future destructive operation; it is not a merge,
transfer, retention, cloud, encryption, history, or Danger Zone feature.
