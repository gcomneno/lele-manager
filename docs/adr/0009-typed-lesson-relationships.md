# ADR 0009: Explicit typed relationships between canonical LeLe

## Decision

LeLe Manager supports explicit typed, directional relationships between
canonical lessons while keeping Markdown as the authority for approved
knowledge.

The maintained public vocabulary is:

- `derives-from`;
- `corrects`;
- `extends`;
- `contradicts`;
- `supersedes`;
- `see-also`.

Five relationship types are stored in the generic canonical `relationships`
frontmatter mapping:

- `derives-from`;
- `corrects`;
- `extends`;
- `contradicts`;
- `see-also`.

`supersedes` is deliberately excluded from that mapping. Supersession already
has one canonical authority defined by ADR 0007: lesson A is superseded by
lesson B when A stores `superseded_by: B`. At read time this is exposed
semantically as B `supersedes` A. A second generic canonical representation of
the same fact is forbidden.

## Canonical Markdown representation

Generic relationships are portable canonical Markdown metadata. A lesson may
contain frontmatter shaped like:

    relationships:
      derives-from:
        - python/base-concept
      corrects:
        - python/older-guidance
      see-also:
        - python/related-example

Relationship keys are rendered in deterministic canonical order:

1. `derives-from`;
2. `corrects`;
3. `extends`;
4. `contradicts`;
5. `see-also`.

Targets inside each type are normalized stable lesson IDs and rendered in
lexical order. Empty relationship types are omitted. If no generic
relationships remain, the `relationships` field itself is omitted.

The ordering is serialization determinism only. It does not imply semantic
priority.

## Direction and reverse navigation

Every generic relationship is directional.

LeLe Manager does not automatically create reciprocal canonical edges,
including for `see-also` and `contradicts`. If the author wants both
directions, both canonical relationships must be authored explicitly.

Only outgoing generic relationships are canonical. Incoming relationships are
derived from the current projection/query state and exposed for navigation;
they are never duplicated into another lesson's canonical Markdown merely to
make reverse lookup convenient.

The same principle applies to supersession: `superseded_by` is canonical on the
superseded lesson and reverse `supersedes` navigation is derived.

## Structural validation

Canonical generic relationships fail validation when:

- `relationships` is not a mapping;
- an unknown relationship type is present;
- `supersedes` is placed in the generic mapping;
- targets are not a list-like sequence of strings;
- a target is blank after trimming;
- a lesson targets itself;
- the same normalized target is repeated within one relationship type.

The same target may legitimately appear under different relationship types.

Generic relationships do not introduce a cycle prohibition. A cycle can be
semantically meaningful for types such as `see-also` or `contradicts`.
Supersession retains its separate cycle prohibition from ADR 0007.

## Explicit authoring boundary

Creating or replacing generic relationships is an explicit user-controlled
canonical mutation.

For an explicit authoring request, every newly supplied target must resolve to
exactly one canonical lesson in the active Vault before the canonical mutation
is written. Missing and ambiguous targets therefore fail closed.

Update semantics distinguish omission from an explicit desired state:

- omitted `relationships` preserves the existing canonical generic
  relationships;
- present `relationships` is the complete desired generic relationship state;
- an explicit empty mapping clears all generic relationships.

The Editor is an explicit authoring surface and sends its complete current
relationship mapping. Adding or removing a relationship in the GUI has no
canonical effect until Save succeeds.

Relationship edits participate in the existing revision-aware canonical
authoring boundary. They use the same exact canonical fingerprint
precondition, stale-write rejection, revision history, and canonical-success
versus derived-refresh-failure semantics defined by ADR 0008.

## Import, projection, and broken references

Projection synchronization reads canonical Markdown; it does not author
relationships.

Structurally valid generic relationships are preserved in the projection even
when a referenced target no longer exists. Existing broken references must not
make an unrelated Vault refresh impossible, because deletion is not a
referential transaction in this decision.

This intentionally differs from explicit authoring validation:

- new explicit relationship authoring requires one exact canonical target;
- import/refresh preserves an already-existing structurally valid edge even if
  the target is currently missing.

Vault Doctor diagnoses unresolved generic references when it has full Vault
context. Missing or ambiguous targets are reported as broken relationships.
Standalone validation without full Vault context performs structural
validation only and must not invent a missing-target diagnostic.

Malformed relationship structure remains a blocking import/Doctor validation
problem.

## API and GUI

Lesson Detail exposes:

- canonical outgoing generic relationships;
- derived incoming generic relationships;
- canonical `superseded_by`;
- derived reverse `supersedes`.

All relationship targets are directly navigable by stable lesson ID.

Editor exposes explicit add/remove controls for the five generic canonical
relationship types. It never offers generic `supersedes` authoring because
that would compete with the maintained `superseded_by` contract.

English and Italian maintained GUI text describe the same author-controlled
behavior.

## Consequences

Typed relationships become durable portable knowledge structure rather than
hidden application inference.

The projection remains rebuildable and can derive reverse navigation without a
graph database. Canonical Markdown remains understandable without LeLe Manager
and retains one source of truth for every maintained relationship fact.

A deleted target may leave a broken generic reference until the user repairs
or removes it. This is visible diagnostic debt rather than a reason to rewrite
or silently discard another lesson's canonical metadata.

## Non-goals

This decision does not:

- introduce a graph database;
- infer canonical relationships from similarity, embeddings, ML, or an
  assistant;
- automatically create reciprocal edges;
- automatically change lifecycle;
- make `contradicts` perform contradiction review or factual verification;
- replace the dedicated supersession contract;
- make deletion referentially transactional;
- automatically repair broken targets;
- implement Context Packs, RAG, or a Vault chatbot.

Freshness/review-needed, contradiction review, and explainable hybrid search
remain separate maintained product gates.
