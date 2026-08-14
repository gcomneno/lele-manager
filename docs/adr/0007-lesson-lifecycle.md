# ADR 0007: Canonical LeLe lifecycle and supersession

## Decision

LeLe lifecycle is maintained canonical metadata stored in Markdown frontmatter. The vocabulary is deliberately small:

- `active` — normal current knowledge;
- `review-needed` — still retained, but explicitly marked for review;
- `deprecated` — no longer recommended as current knowledge;
- `archived` — retained historical knowledge outside normal current retrieval.

`active` is the implicit default. Existing canonical Markdown without a `lifecycle` field is therefore active and does not need a migration rewrite. Writers omit the redundant `lifecycle: active` field.

Lifecycle transitions are explicit user-authored canonical mutations. Freshness, similarity, contradiction detection, model output, or other derived signals may suggest review but never silently change canonical lifecycle.

## Supersession

A canonical lesson may contain one optional `superseded_by` stable ID identifying its maintained replacement. The reference must:

- be non-empty when present;
- differ from the lesson's own stable ID;
- resolve to exactly one existing canonical lesson in the active Vault;
- not create a supersession cycle.

The forward reference is stored only on the superseded lesson. Incoming/reverse navigation is derived from the projection at read time rather than duplicated into canonical Markdown.

Supersession does not delete, merge, rewrite, or automatically change the lifecycle state of either lesson. The user remains responsible for choosing the intended lifecycle explicitly.

## Retrieval and export

Normal Browse and search default to `active` only. Callers can explicitly request any subset of maintained lifecycle states, including all states. Detail remains addressable by stable ID regardless of lifecycle so historical knowledge and supersession links never become inaccessible.

Search export uses the same lifecycle scope. Exported Markdown preserves non-default lifecycle metadata and `superseded_by`; active lessons omit redundant lifecycle metadata.

Non-active lifecycle must be visually explicit in Browse cards and Detail. The product must not make deprecated or archived knowledge look indistinguishable from current active knowledge.

## Authoring compatibility

The canonical update boundary distinguishes omitted lifecycle fields from explicit lifecycle edits. Maintained older callers that update text/topic/tags without supplying lifecycle preserve the existing canonical lifecycle and supersession metadata. The Editor supplies lifecycle explicitly, so selecting Active intentionally clears a previous non-active lifecycle marker, and clearing the replacement intentionally removes `superseded_by`.

## Projection and validation

Import projects normalized lifecycle and supersession fields from canonical Markdown. Invalid lifecycle values, invalid self-supersession, or malformed replacement metadata are validation failures rather than silently being treated as active. Active remains the default only for genuinely absent/blank lifecycle metadata.

This ADR establishes the lifecycle/supersession foundation consumed by revision history, freshness, contradiction review, and typed relationships. It does not implement automatic freshness transitions, automatic deprecation, or a general relationship vocabulary; those remain separate maintained workflows.
