# ADR 0006: Preview-first per-Vault danger zone

## Decision

Destructive Vault lifecycle operations live in a visually and semantically separate **Danger zone / Zona pericolosa** under System. Authority is always an explicit registered Vault UUID resolved again at execution time; display names and filesystem paths are review information, never authority.

Every operation is preview-first and stateless. The plan digest binds the operation, registered target context, active-Vault identity, exact canonical Markdown state, and every scoped persistent state that the selected operation may destroy. `Merge and delete source` additionally binds the explicit destination context and its exact canonical state. A changed target, registry context, canonical file, relevant candidate/duplicate-decision state, active selection, or merge destination makes the plan stale before destruction starts.

## Operations

### Empty Vault

Deletes all approved canonical Markdown from the selected Vault, preserving:

- the registered Vault identity;
- the Vault directory;
- candidate staging;
- duplicate-review decisions.

After actual canonical deletion, derived projection/search state is reconciled to the resulting canonical Vault. A canonical partial failure remains authoritative and is reported independently from any derived refresh failure.

### Reset Vault completely

Deletes:

- approved canonical Markdown;
- Vault-scoped candidate staging;
- Vault-scoped duplicate-review decisions;
- Vault-scoped projection and topic-model state.

The Vault registration and directory remain. Editorial state is cleared only after canonical deletion completes; a partial canonical deletion does not silently continue into additional editorial destruction. Derived state is either cleared after a complete reset or reconciled to the actual remaining canonical state after a partial canonical deletion.

### Delete Vault from disk

Physical Vault deletion is allowed only for a non-active registered Vault. Before any mutation LeLe Manager recursively proves that the target directory contains only real directories and regular `.md` files. Symlinks, special filesystem nodes, and non-Markdown regular files block the operation. This prevents the product from deleting files it cannot prove belong to its managed canonical namespace.

After exact canonical deletion and removal of the now-empty managed directory, LeLe Manager clears Vault-scoped candidate, duplicate-review, projection/model/cache state and then removes the registry entry. Filesystem, scoped-state, and registry outcomes are reported independently when a later phase fails.

### Merge and delete source

This is a separate destructive operation built on #193; it never trusts a transient UI/session receipt. At preview and again immediately before mutation, every source canonical lesson must be represented in the explicit destination by:

1. the same stable lesson ID; and
2. byte-for-byte identical canonical Markdown.

Material fingerprints, semantic similarity, path coincidence, or a previous merge response are insufficient authority. The source must be inactive and physical deletion follows the same safe-tree contract as `Delete Vault from disk`.

## Typed confirmation

Each preview returns the exact phrase required for execution:

- `EMPTY <Vault name>`;
- `RESET <Vault name>`;
- `DELETE <Vault name>` for physical deletion operations.

Changing the Vault name invalidates the plan because the registered context and confirmation phrase are plan-bound. A generic yes/no dialog is never sufficient.

## Backup contract

Every destructive preview offers **Create snapshot backup before continuing / Crea snapshot di backup prima di continuare**. When selected, the maintained snapshot artifact is created and atomically persisted under local LeLe Manager data storage before the first destructive canonical mutation. Any requested backup failure aborts execution before destruction.

The snapshot contains managed canonical Markdown plus scoped candidate and duplicate-review state. Physical Vault deletion refuses foreign non-Markdown files, so the maintained snapshot remains an honest backup of the product-owned state being destroyed.

## Isolation and partial success

Danger-zone actions never switch the active Vault, never infer a target from an active label, and never mutate another registered Vault. Registry overlap invariants and safe execution-time resolution remain in force.

Canonical, editorial, derived, filesystem-directory, and registry outcomes are distinct. Once a phase has succeeded, a later failure is reported as partial success rather than rewriting history or claiming rollback. No automatic cloud upload, hidden backup, semantic merge, or arbitrary path deletion is introduced by this ADR.
