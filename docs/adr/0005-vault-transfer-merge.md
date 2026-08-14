# ADR 0005: Preview-first registered Vault transfer

## Decision

Vault-to-Vault **Merge**, **Copy**, and **Move** operate only on two distinct
registered Vault UUIDs and an explicit lesson selection. Display names and paths
are review information, never authority. Neither preview nor execution changes
the active Vault or registry selection.

`merge` and `copy` are non-destructive to the source. `move` may delete a source
lesson only after the destination canonical contract has succeeded and has been
verified again immediately before deletion. This ADR does not implement
whole-Vault deletion; that remains future #194 Danger Zone work.

## Preview and classification

Preview is read-only, stateless, and uses the hardened canonical Markdown
filesystem boundary maintained by #218. It does not create projection, cache,
model, candidate, or duplicate-decision state.

Each selected source lesson has exactly one classification:

- `new`: no destination stable-ID/path conflict and no maintained duplicate match;
- `identical`: the same canonical path contains byte-for-byte identical Markdown;
- `already_present`: the same stable ID exists at another canonical path with
  byte-for-byte identical Markdown;
- `same_id`: the stable ID exists but canonical Markdown bytes differ;
- `path_conflict`: the requested canonical path belongs to another lesson;
- `likely_duplicate`: #184 maintained duplicate semantics identify a possible
  duplicate after identity/path checks.

The duplicate-review `material_fingerprint` remains useful semantic state, but
it is deliberately **not** canonical equivalence. Casing, whitespace, line
endings, and tag presentation can normalize to the same material fingerprint
while representing different canonical bytes.

Conflicts never overwrite destination Markdown. `same_id`, `path_conflict`, and
`likely_duplicate` require an explicit `keep_destination` or `skip`; a changed
resolution invalidates the displayed plan and requires a new preview. There is
no automatic semantic merge or silent identity rewrite.

The plan digest binds transfer-semantics version, operation, both resolved
registered contexts, complete source/destination canonical state, exact
selection, classifications, and resolutions. Execution recomputes the plan
statelessly. A source, destination, operation, selection, resolution, registry
context, or canonical-state change produces a stale-plan failure before the
planned mutation begins.

## Mutation and result buckets

Destination canonical create is atomic and create-only; a late collision never
overwrites. Results distinguish:

- `destination_written`: new destination canonical bytes were created;
- `destination_already_exact`: exact canonical content already existed, so the
  destination is a no-op;
- `skipped_by_resolution`: the user retained destination/skipped a conflict;
- `destination_write_failed`: destination create failed and source is untouched;
- `move_destination_verification_failed`: MOVE could not re-prove exact
  destination bytes, so source is untouched;
- `move_source_delete_failed`: destination remains but source deletion failed;
- `moved`: exact destination was verified and source canonical deletion succeeded.

Destination derived reconciliation runs only when at least one destination
canonical file was newly written. Exact/no-op or user-skipped items do not
invalidate or rebuild destination derived state.

For MOVE, destination canonical bytes are reverified immediately before each
source deletion. A newly written destination may remain canonical-successful
even if destination derived reconciliation fails; because derived state is
rebuildable, MOVE may still delete the source after exact destination
verification. That partial result is reported truthfully. Source derived
reconciliation runs only after at least one actual source canonical deletion.
A source-delete failure never rolls back an already-successful destination.

## Isolation and relationship to other work

Only approved canonical Markdown is transferred. Candidate/editorial staging and
duplicate-review decisions never cross Vault scopes. Unrelated Vaults, including
a third Vault C, are untouched. Derived projection/model/cache invalidation is
scoped only to a Vault whose canonical state actually changed.

#218 supplies the hardened canonical filesystem boundary and safe create/delete
primitives used here. Future #194 may build separately confirmed destructive
whole-Vault workflows on top of verified transfer results; #193 itself never
deletes a Vault or its registry entry.
