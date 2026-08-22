# Issue 215: Potential contradiction review implementation plan

## Binding contract summary

Issue #215 implements potential contradiction candidate surfacing only. It does
not implement factual verification.

Issue-language corrections are binding:

- "contradiction detection" means potential-candidate surfacing;
- "semantic evidence" and "opposing terms" are deterministic review cues, not
  proof;
- lifecycle changes are outside minimum #215;
- "true-positive" means expected candidate-surfacing scenario.

Candidate generation is read-only, bounded and explainable. A pair is eligible
only when both lessons are `active` or `review-needed`, the pair is not already
canonically resolved, the lessons are not exact duplicates, the pair passes a
same-subject gate and at least one deterministic tension cue is present.

The maintained reason vocabulary is:

- `same-topic`;
- `shared-tags`;
- `similarity-gate`;
- `negated-shared-phrase`;
- `opposing-modal-cue`;
- `opposing-term-cue`;
- `version-or-date-context`;
- `different-source-context`.

Similarity, TF-IDF, LSA and cosine are retrieval/gating metadata only. Shared
tags or similarity alone are insufficient for surfacing.

Auxiliary contradiction-review state is durable Vault-scoped
editorial/workflow state, not canonical knowledge and not a rebuildable
projection. It uses normalized pair identity, material fingerprints, schema
version and generator version. The material fingerprint covers body/text,
title, topic, source, date, tags, lifecycle, `superseded_by` and
relationships.

Changed material invalidates prior auxiliary suppression.
`different-context` and `dismissed` are auxiliary decisions only and never
mutate Markdown.

Canonical resolutions are explicit and directional:

- `superseded-by` writes only `superseded_by` on the superseded lesson;
- `corrects` writes only the selected correcting/source relationship edge;
- `contradicts` writes only the explicitly selected directional source edge;
- reciprocal `contradicts` edges are never created automatically;
- generic canonical `supersedes` is never created;
- lifecycle is never changed automatically.

All canonical resolutions use the ADR 0008 revision-aware canonical authoring
boundary. ADR 0008 canonical revision remains the separate stale-write token.
Stale revisions, ambiguous IDs and missing IDs fail closed. Canonical success
and derived refresh failure are separate outcomes.

For snapshots/backups, the contradiction-review store is durable editorial
state, so runtime transparency must expose it. Existing portable snapshots
must not be silently described as preserving it. Snapshot integration and
schema compatibility remain a separate compatibility decision unless the
accepted snapshot contract is revised to include the store.

Duplicate-review implementation may be reused only as patterns. Do not
collapse semantics or stores.

## Proposed file/change map

Expected production implementation areas:

- `src/lele_manager/core/`: domain models for pair identity, material
  fingerprint, reason vocabulary, auxiliary decisions and resolution intents.
- `src/lele_manager/application/`: candidate generation, suppression,
  canonical-resolution orchestration and derived reconciliation outcomes.
- `src/lele_manager/adapters/`: Vault-scoped durable auxiliary store with
  versioned schema, validated reads, atomic replacement and safe failure.
- `src/lele_manager/api/`: bounded candidate/explanation endpoints,
  auxiliary-decision endpoint and explicit canonical-resolution endpoint.
- `frontend/`: English/Italian review UI that distinguishes potential
  candidates, auxiliary decisions and canonical writes.
- `src/lele_manager/gui/static/`: regenerated GUI assets only after frontend
  source changes are complete.
- `tests/`: focused unit, application, adapter, API and GUI/E2E coverage.
- `docs/`: follow-up documentation updates only if implementation changes the
  accepted contract.

This materialization step creates only:

- `docs/adr/0011-potential-contradiction-review.md`;
- `docs/issue-215-contradiction-review-plan.md`.

## Ordered implementation phases

1. Domain contract

   Add typed values for normalized contradiction pair identity, material
   fingerprint input, maintained reasons, candidate explanation, auxiliary
   decisions and canonical resolution intents. Keep exact duplicates and
   canonically resolved-pair checks explicit.

2. Candidate generation

   Implement a read-only bounded generator. Apply lifecycle scope, exact
   duplicate exclusion, canonical-resolution exclusion, same-subject gate,
   deterministic tension cue requirement, deterministic scoring and stable
   ordering. Apply the visible result limit after suppression.

3. Auxiliary store

   Add the Vault-scoped durable contradiction-review store with schema version,
   generator version, normalized pair keys, material fingerprints, validated
   reads, same-process serialization and atomic replacement. Malformed state
   fails closed for state-dependent operations.

4. Application resolution workflow

   Implement auxiliary-only `different-context` and `dismissed` decisions.
   Implement explicit canonical-resolution orchestration for `superseded-by`,
   `corrects` and `contradicts` through ADR 0008. Preserve partial-success
   reporting when canonical mutation succeeds and derived refresh fails.

5. API

   Expose candidate list/explanation, auxiliary decisions and canonical
   resolution requests. Require current canonical revision tokens for canonical
   writes. Fail closed for stale revisions, missing IDs and ambiguous IDs.

6. GUI and localization

   Add English and Italian review flows that consistently say potential
   candidate/review, never verified contradiction. Make direction explicit for
   canonical writes and distinguish auxiliary suppression from Markdown
   mutation.

7. Runtime transparency and compatibility follow-up

   Expose the presence/location/health of the durable contradiction-review
   store in runtime transparency surfaces. Treat portable snapshot inclusion
   as a separate compatibility decision unless the accepted snapshot contract
   is revised.

## Test matrix mapped to phases

Phase 1:

- normalized unordered pair identity is stable;
- material fingerprint changes when body/text, title, topic, source, date,
  tags, lifecycle, `superseded_by` or relationships change;
- maintained reason vocabulary rejects unknown reasons;
- duplicate-review types and contradiction-review types remain separate.

Phase 2:

- candidate surfaces from same subject plus deterministic tension cue;
- similarity alone is insufficient;
- shared tags alone are insufficient;
- exact duplicates are excluded;
- canonically resolved pairs are excluded;
- only `active` and `review-needed` lessons are eligible;
- deterministic ordering holds with score ties;
- deterministic ordering holds with shuffled input;
- result limit is applied after suppression;
- "true-positive" fixtures assert expected candidate surfacing, not truth.

Phase 3:

- `different-context` suppression hides a candidate while fingerprints match;
- `dismissed` suppression hides a candidate while fingerprints match;
- changed material reappears after prior suppression;
- malformed auxiliary store fails safely and visibly;
- decisions are isolated by Vault UUID;
- auxiliary decisions never mutate Markdown;
- runtime transparency exposes the durable store;
- existing portable snapshot behavior is not silently asserted to preserve the
  new store.

Phase 4:

- `corrects` writes only the selected directional correcting/source edge;
- `contradicts` writes only the explicitly selected directional source edge;
- reciprocal `contradicts` is not automatically created;
- `superseded-by` writes only `superseded_by` on the superseded lesson;
- generic canonical `supersedes` is never created;
- no automatic lifecycle change occurs;
- stale revision rejection fails closed;
- ambiguous canonical IDs fail closed;
- missing canonical IDs fail closed;
- canonical success plus derived refresh failure is reported as partial
  success.

Phase 5:

- API candidate responses include explainable same-subject and tension reasons;
- API wording and payload semantics avoid factual-verification claims;
- canonical-resolution endpoints require the ADR 0008 stale-write token;
- auxiliary-only endpoints do not accept canonical mutation fields.

Phase 6:

- English GUI text says potential candidate/review semantics;
- Italian GUI text says the same semantics;
- no GUI string implies factual verification, proof or automatic truth
  judgment;
- direction selection is visible for `superseded-by`, `corrects` and
  `contradicts`;
- auxiliary decisions and canonical writes are visually distinct.

Phase 7:

- runtime transparency reports contradiction-review store state per Vault;
- Vault isolation tests prove decisions from one Vault do not suppress another
  Vault;
- snapshot/backups tests either prove an explicit accepted schema integration
  or prove the implementation does not silently claim preservation.

## Validation gates

- Focused unit tests for domain identity, fingerprinting, reason validation and
  eligibility.
- Application tests for generation ordering, suppression, changed-material
  invalidation and canonical-resolution orchestration.
- Adapter tests for auxiliary store versioning, malformed state, atomic write
  behavior and Vault isolation.
- API tests for bounded listing, explanation payloads, stale revisions,
  missing/ambiguous IDs and partial success.
- GUI/E2E tests for EN/IT semantics, directionality and absence of
  factual-verification wording.
- Existing duplicate-review tests remain valid without semantic collapse.
- Existing ADR 0007, ADR 0008 and ADR 0009 behavior remains unchanged.
- `git diff --check` passes before handoff.

## Semantic traps and explicit prohibitions

- Do not perform factual verification.
- Do not describe candidates as proven contradictions.
- Do not treat semantic evidence, opposing terms, similarity or shared tags as
  proof.
- Do not surface candidates from similarity/shared tags alone.
- Do not include exact duplicates.
- Do not include already canonically resolved pairs.
- Do not mutate Markdown from candidate generation.
- Do not let `different-context` or `dismissed` mutate Markdown.
- Do not store auxiliary decisions as canonical knowledge.
- Do not treat auxiliary decisions as rebuildable projection state.
- Do not reuse duplicate-review stores or collapse duplicate and contradiction
  semantics.
- Do not write canonical relationships outside the ADR 0008 authoring
  boundary.
- Do not ignore stale canonical revisions.
- Do not auto-create reciprocal `contradicts`.
- Do not create generic canonical `supersedes`.
- Do not automatically change lifecycle.
- Do not report derived refresh failure as canonical mutation failure.
- Do not silently claim existing portable snapshots preserve the new durable
  contradiction-review store.

## Definition of done

- ADR 0011 is accepted and matches the implemented behavior.
- Candidate generation is read-only, bounded, explainable and deterministic.
- Eligibility requires same subject plus at least one deterministic tension
  cue.
- Exact duplicates and canonically resolved pairs are excluded.
- Auxiliary suppression is durable, Vault-scoped and invalidated by changed
  material.
- Auxiliary decisions never mutate canonical Markdown.
- Canonical resolutions are explicit, directional and revision-aware.
- Stale revisions, missing IDs and ambiguous IDs fail closed.
- Canonical success and derived refresh failure are reported separately.
- Lifecycle never changes automatically.
- English and Italian GUI semantics consistently describe potential candidate
  review.
- Tests cover every matrix item above.
- Runtime transparency exposes the durable contradiction-review store.
- Snapshot/schema compatibility for the new store is either explicitly decided
  or left as an acknowledged separate compatibility decision.
