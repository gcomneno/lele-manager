# ADR 0003: Stable multi-Vault registry

## Decision

LeLe Manager stores a versioned `vault-registry.json` in application data. Its
schema version is `1` and contains `active_vault_id` plus immutable UUID-backed
Vault records (`id`, display `name`, resolved absolute `path`, and
`registered_at`). The registry is persistent application state, not canonical
knowledge. Writes are process-locked and atomically replaced; malformed or
unsupported registries are reported and never replaced or silently bypassed.

An operation resolves one immutable `ActiveVaultContext`. It carries the
registered ID, display name, canonical Markdown root, projection, candidate
staging document, topic-model cache, and duplicate-decision scope. Runtime
artifacts are keyed by the stable ID:

```
data/vaults/<id>/lessons.jsonl
data/vaults/<id>/candidates.json
cache/vaults/<id>/topic_model.joblib
```

Duplicate decisions remain in the global application document but their normal
scope is the UUID. Version-1 path scopes migrate to the bootstrap Vault when
known; unmatched scopes are retained as explicit legacy state.

Bootstrap writes the registry and its stable bootstrap UUID before migration.
The registry records candidate and duplicate-decision phase completion for that
same UUID. A later bootstrap resumes only incomplete phases: candidate staging
is moved without overwrite, then the matching path-scoped decisions are moved
idempotently. Each completed phase is persisted immediately; only after both
succeed does a final completion marker prevent all future legacy-file scans.
Failures preserve the registry, legacy state, and any already completed phase
for a safe retry; a conflict with both candidate documents remains explicit.

## Compatibility and activation

Before a registry exists, `LELE_VAULT_DIR` is only a bootstrap source (otherwise
the historical `~/LeLeVault` is registered). Once valid registry state exists,
its active ID is authoritative: changing the environment variable cannot switch
the workspace. `LELE_DATA_PATH` and `LELE_MODEL_PATH` are legacy artifact
sources and are not runtime authorities in managed multi-Vault operation.

Activation first verifies the registered directory and reconciles its scoped
projection with `write_missing_frontmatter=False`; only then is the active ID
persisted and the similarity cache invalidated. A failed activation leaves the
old active Vault selected. Registering and switching never write canonical
Markdown. Candidate staging migrates from the historical global document only
for the bootstrap Vault and never overwrites a scoped document.

## Boundaries

This establishes context and isolation only. Snapshot/restore is #218,
cross-Vault transfer is #193, and filesystem deletion/reset is #194. Removing a
Vault from Manager only removes registry membership and cannot remove the active
Vault or any filesystem content.
