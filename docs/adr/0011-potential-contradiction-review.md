# ADR 0011: Potential contradiction review

## Decision

LeLe Manager surfaces potential contradiction candidates between canonical
lessons for human review.

This is candidate surfacing only. It is never factual verification and never a
claim that one lesson is wrong. In issue language, "contradiction detection"
means potential-candidate surfacing; "semantic evidence" and "opposing terms"
are deterministic review cues, not proof; and a "true-positive" means an
expected candidate-surfacing scenario.

Candidate generation is read-only, bounded and explainable. It may inspect
canonical lesson material and derived retrieval metadata, but it must not
mutate Markdown, lifecycle, relationships, projection state, revision history
or auxiliary contradiction decisions.

## Authority boundaries

Canonical Markdown remains the authority for approved lesson knowledge.
Auxiliary contradiction-review state is durable editorial/workflow state. It is
not canonical knowledge and not a rebuildable projection.

The contradiction-review workflow can propose that a human author make a
canonical change, but canonical mutation remains a separate explicit operation
through the maintained ADR 0008 revision-aware canonical authoring boundary.

Similarity, TF-IDF, LSA, cosine distance and related model outputs are
retrieval or gating metadata only. They may help identify pairs worth checking,
but they are not evidence of factual contradiction and cannot by themselves
make a pair eligible.

Duplicate-review implementation may be reused only as implementation patterns,
such as Vault scoping, normalized pair identity, validated stores, atomic
replacement or deterministic ordering. Its semantics and stores must not be
collapsed with contradiction review.

## Candidate eligibility

A surfaced pair must satisfy all of these requirements:

- both lessons belong to the same registered Vault;
- both lessons are in the reviewable lifecycle scope: `active` or
  `review-needed`;
- the pair has not already been canonically resolved;
- the lessons are not exact duplicates;
- the lessons pass a same-subject gate;
- at least one deterministic tension cue is present.

Already canonically resolved pairs are excluded. A pair is resolved when the
current canonical material already records a maintained resolution between the
two lessons, including `superseded_by`, a `corrects` relationship edge or an
explicit `contradicts` relationship edge in either relevant direction.

Exact duplicates are excluded because they belong to duplicate review, not
contradiction review.

The same-subject gate may use topic, normalized title, shared maintained tags,
or retrieval metadata to establish that the two lessons are about the same
subject. Shared tags or similarity alone are insufficient; the pair also needs
a deterministic tension cue.

The maintained reason vocabulary is:

- `same-topic`;
- `shared-tags`;
- `similarity-gate`;
- `negated-shared-phrase`;
- `opposing-modal-cue`;
- `opposing-term-cue`;
- `version-or-date-context`;
- `different-source-context`.

The first three reasons explain subject or retrieval gates. The remaining
reasons explain deterministic tension/context cues. `different-source-context`
can explain why a pair was surfaced for review, but it does not prove a
contradiction.

## Explainability

Every candidate response records why the pair was eligible in maintained,
deterministic terms.

Explanations must identify:

- the normalized pair identity;
- the participating lesson IDs and titles;
- lifecycle values considered for eligibility;
- same-subject reasons;
- deterministic tension cues;
- optional retrieval/gating metadata such as similarity score;
- whether an auxiliary decision suppressed the pair;
- whether changed material invalidated an earlier suppression.

Scores must be presented as prioritization or retrieval metadata only. UI, API
and documentation text must avoid factual-verification wording.

## Auxiliary decision state

The auxiliary contradiction-review store is durable per-Vault editorial state
under application data scoped by immutable Vault UUID.

Each decision is keyed by normalized unordered pair identity and stores:

- the two stable lesson IDs in normalized order;
- decision value;
- UTC timestamp;
- optional human note;
- material fingerprints for both lessons;
- schema version;
- generator version.

The material fingerprint covers the canonical material relevant to
contradiction review:

- body/text;
- title;
- topic;
- source;
- date;
- tags;
- lifecycle;
- `superseded_by`;
- relationships.

Changed material invalidates prior auxiliary suppression. If either current
material fingerprint differs from the fingerprint stored with a suppressing
decision, the pair may reappear as a candidate.

Malformed, unsupported or unsafe auxiliary store state fails closed for
state-dependent operations. It must not be treated as an empty clean store
when that would silently lose editorial decisions.

## Human resolution vocabulary

The maintained human decisions are:

- `different-context`;
- `dismissed`;
- `superseded-by`;
- `corrects`;
- `contradicts`.

`different-context` and `dismissed` are auxiliary decisions only. They suppress
the current pair while its material fingerprints remain current and never
mutate canonical Markdown.

`superseded-by`, `corrects` and `contradicts` are canonical-resolution intents.
They require an explicit canonical mutation request with a current ADR 0008
expected revision token for the lesson that will be written.

Lifecycle changes are outside the minimum issue #215 scope. No auxiliary or
canonical contradiction-review action automatically changes lifecycle.

## Directionality

Canonical resolutions are directional where the underlying canonical field is
directional.

`superseded-by` writes only `superseded_by` on the superseded lesson.

`corrects` writes only the selected `corrects` relationship edge from the
correcting lesson to the source lesson being corrected.

`contradicts` writes only the explicitly selected directional source edge. LeLe
Manager never automatically creates reciprocal `contradicts` edges. If a human
author wants both directions, both edges must be explicitly authored.

Contradiction review must never create generic canonical `supersedes`.
Supersession has one canonical representation: `superseded_by` on the
superseded lesson.

## Canonical mutation and concurrency

All canonical resolutions use the maintained ADR 0008 revision-aware canonical
authoring boundary.

Before mutation, all referenced canonical lesson IDs must resolve to exactly
one lesson in the active Vault. Missing or ambiguous IDs fail closed.

The operation requires the caller-provided exact canonical revision/fingerprint
for the lesson being mutated. Inside the canonical mutation boundary the
application re-resolves the lesson and recomputes the exact current
fingerprint. A stale canonical revision fails closed and must not be silently
retried against newer Markdown.

Canonical success and derived refresh failure are separate outcomes. A
successful Markdown mutation remains successful even if projection or
candidate refresh later fails.

## Lifecycle interaction

Candidate surfacing considers only `active` and `review-needed` lessons.

Contradiction review never automatically changes lifecycle. Marking either
lesson `review-needed`, `deprecated`, `archived` or back to `active` is a
separate explicit canonical lifecycle mutation governed by ADR 0007 and ADR
0008.

## Derived reconciliation / partial success

After a canonical contradiction-review resolution succeeds, LeLe Manager runs
the maintained derived reconciliation for the affected Vault.

If derived refresh fails after canonical success:

- canonical Markdown remains the approved authority;
- the API reports canonical success plus derived refresh failure as partial
  success;
- the auxiliary decision/candidate view must not report that the canonical
  mutation failed;
- the user can retry derived reconciliation without repeating the canonical
  mutation.

Candidate generation after reconciliation reads current canonical material and
current auxiliary editorial state. It must exclude pairs already resolved by
the new canonical Markdown.

## API and UI

The API exposes bounded candidate listing, candidate explanation, auxiliary
decisions and explicit canonical-resolution requests.

Candidate list results are deterministic. Ordering must remain stable for
equal scores and shuffled input by using maintained tie breakers such as
normalized lesson IDs and reason order. Limits apply after canonical-resolution
exclusion and auxiliary suppression so the caller receives up to the requested
number of visible candidates.

The GUI must describe the workflow in English and Italian as review of
potential contradiction candidates. It must not present candidates as verified
contradictions or factual errors.

Resolution controls must make direction explicit for `superseded-by`,
`corrects` and `contradicts`. Auxiliary decisions must be visually distinct
from canonical writes.

## Vault isolation / durable editorial state

Contradiction-review state is scoped to exactly one registered Vault UUID. One
operation must use one coherent Vault context. Candidate generation,
suppression and canonical resolution must not mix pair identity, material
fingerprints or decisions across Vault IDs.

Because the contradiction-review store is durable editorial/workflow state,
runtime transparency must expose it alongside other non-rebuildable per-Vault
state.

Portable snapshot integration is a separate compatibility decision unless the
accepted snapshot contract is explicitly revised to include this store. The
current schema version 1 snapshot contract names canonical Markdown,
`editorial/candidates.json` and `editorial/duplicate-decisions.json`; this ADR
does not silently claim existing portable snapshots preserve the new
contradiction-review store.

## Non-goals

This decision does not:

- perform factual verification;
- decide which lesson is true;
- use model similarity as proof;
- automatically create canonical relationships;
- automatically create reciprocal `contradicts`;
- create generic canonical `supersedes`;
- automatically change lifecycle;
- merge contradiction-review state with duplicate-review state;
- make auxiliary contradiction decisions canonical knowledge;
- make auxiliary contradiction decisions rebuildable projection state;
- change portable snapshot schema compatibility by implication.

## Consequences

Users get a bounded, explainable review queue for likely tension between
lessons while Markdown remains the knowledge authority.

The design preserves the separation between canonical knowledge, durable
editorial workflow state and rebuildable retrieval/projection metadata.

The system must maintain additional per-Vault durable state and expose its
presence operationally. Backup/export compatibility for that state requires an
explicit snapshot/schema decision rather than an accidental extension of the
existing snapshot format.
