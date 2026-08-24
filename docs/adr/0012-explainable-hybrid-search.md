# ADR 0012: Explainable hybrid search

## Decision

LeLe Manager provides one maintained hybrid-search experience that combines
deterministic lexical matching, bounded semantic similarity and maintained
metadata signals.

Hybrid search is a retrieval and prioritization capability. It is advisory and
does not grant authority to mutate canonical Markdown, lifecycle, relationships
or any other authoritative state.

The ordinary user should not need to select or tune an underlying retrieval
engine. Maintained defaults compose the available signals behind one search
surface.

## Authority boundaries

Canonical Markdown remains the authority for approved lesson knowledge.

Search operates on the maintained queryable projection and rebuildable
similarity artifacts. Search ranking, similarity scores, freshness assessments
and result explanations are derived retrieval state only.

A high rank never means that a result is true, current, approved beyond its
canonical lifecycle, or preferable as canonical knowledge.

Search must preserve the existing projection-freshness contract. Stale
projection state must not be silently presented as current.

## Application boundary

Hybrid-search orchestration belongs in the application layer.

The HTTP API, CLI and GUI may translate user requests and render results, but
they must not independently implement ranking semantics.

The application search boundary owns:

- filter composition;
- lexical signal extraction;
- optional semantic retrieval;
- maintained metadata signals;
- score composition;
- deterministic ordering;
- concise result explanations;
- bounded result limiting.

Similarity remains a subordinate retrieval capability behind its existing
service/backend boundary. Hybrid search must not collapse the similarity
backend into the API contract.

## Query behavior

Ordinary search uses one retrieval query plus maintained eligibility filters.

For hybrid search, `q` is a retrieval query, not a mandatory substring
eligibility filter.

This intentionally changes the current behavior in which `q` removes every
lesson whose body/text does not contain the query substring before ordering.
Keeping that behavior would make semantic retrieval unable to surface a
conceptually relevant non-lexical result and would therefore defeat the hybrid
search contract.

Eligibility filters remain separate and include maintained constraints such as:

- topic scope;
- source scope;
- importance range;
- lifecycle scope;
- freshness-review scope.

The retrieval query may produce deterministic lexical evidence from maintained
fields such as:

- title;
- body/text;
- topic;
- tags;
- source.

It may also produce optional semantic evidence through the maintained
similarity boundary.

A lesson therefore may be eligible for a non-empty query without containing
the literal query substring when bounded semantic evidence makes it a relevant
candidate.

The maintained implementation must normalize text deterministically for
matching and ranking. Exact and phrase-level matches must remain explainable
and protected.

When no text query is supplied, search remains a deterministic filtered browse
operation. It does not fabricate lexical or semantic relevance from an empty
query.

## Lexical protection

Strong deterministic lexical matches receive protected ranking precedence.

In particular, an exact or strong direct lexical match must not be unexpectedly
buried below a result whose advantage comes only from opaque semantic
similarity.

The maintained ranker may distinguish lexical strengths such as:

- exact title match;
- exact phrase match;
- title contains query;
- body/text contains query;
- metadata token overlap.

The exact maintained vocabulary and weights are implementation contract, not
user-tunable parameters.

Lexical protection is a ranking rule, not a claim that lexical retrieval is
always semantically superior.

## Semantic similarity

Semantic similarity complements lexical retrieval; it does not replace it.

The existing similarity service/backend remains the maintained computation
boundary.

Hybrid search may use semantic similarity only when:

- a non-empty text query is present;
- the required local similarity model/artifact is available and valid;
- the operation remains within maintained bounds.

If semantic retrieval is unavailable, ordinary hybrid search degrades to the
available deterministic lexical and metadata signals rather than failing the
entire search solely because the optional similarity artifact is absent.

Semantic degradation must be observable in maintained result/search metadata
where useful, but normal users must not be forced to understand model
internals.

Hybrid search does not expose raw `top_k`, `min_score`, backend names or model
tuning in the ordinary search workflow.

## Metadata signals

Maintained metadata may contribute bounded ranking signals where relevant and
explainable.

Initial #219 signals may include:

- topic match;
- shared/matching tags;
- source match;
- importance;
- date/recency;
- lifecycle state;
- derived freshness/review attention.

Metadata filters and metadata ranking signals are distinct:

- filters decide eligibility;
- query-to-metadata matches may contribute relevance evidence;
- bounded query-independent priors may participate only where the maintained
  ranking contract explicitly defines them.

A filter value must not be counted as relevance merely because the caller
selected it. For example, restricting the search to one topic does not itself
mean every result receives a `topic-match` relevance bonus.

Conversely, when the retrieval query itself matches a lesson topic, tag or
source, that match may be legitimate explainable ranking evidence.

Importance, date, lifecycle or freshness must not be strong enough by
themselves to bury a protected direct lexical match.

## Lifecycle policy

Lifecycle remains primarily an eligibility policy.

The maintained default remains `active` only when lifecycle scope is omitted.

Power users may explicitly include:

- `review-needed`;
- `deprecated`;
- `archived`.

Lifecycle state may appear in explanations, but lifecycle is not a truth score.

Including deprecated or archived knowledge explicitly must remain composable
with lexical, semantic and metadata ranking.

No search operation changes lifecycle.

## Freshness policy

Freshness is advisory review metadata.

Freshness may be shown in result explanations and may provide a bounded
prioritization signal where the maintained implementation defines one.

A freshness signal must never be described as proof that knowledge is wrong or
outdated.

Search filtering by `freshness_review_needed` remains composable with hybrid
ranking.

## Relationships

Typed lesson relationships are not required as a ranking signal for the initial
#219 implementation.

They may become a future bounded signal under a separate accepted contract.

Search must not opportunistically add relationship-based ranking merely because
relationship data is available.

## Ranking model

Hybrid ranking must be deterministic and bounded.

The implementation must use maintained constants or a maintained ranking
configuration. Ordinary users do not tune weights.

The composed rank must preserve these invariants:

1. eligibility filters apply before final ranking;
2. protected direct lexical matches cannot be unexpectedly buried by
   semantic-only results;
3. semantic similarity is bounded;
4. metadata contributions are bounded;
5. ties resolve deterministically using maintained stable keys, ultimately
   including lesson ID;
6. the visible limit applies after ranking.

The implementation may use a numeric internal score, ordered score tuple, tier
model, or equivalent deterministic representation, provided these invariants
remain explicit and covered by tests.

Raw implementation weights are not required in user-facing explanations.

## Explainability

Every ranked result can expose a concise `Why this result?` explanation.

Explanations are generated from the same maintained signals that influenced
ranking. They must not be decorative or reconstructed independently from the
actual scoring decision.

The API should expose stable machine-readable reason codes plus bounded
structured values needed for rendering.

Initial explanation concepts may include:

- exact title match;
- exact phrase match;
- title/text lexical match;
- topic match;
- matching/shared tags;
- source match;
- semantic similarity;
- importance;
- lifecycle state;
- freshness/review attention.

The final maintained reason vocabulary is fixed by implementation and tests.

GUI text is localized in English and Italian. User-facing explanations should
describe useful reasons, not raw engine internals.

## API compatibility

`POST /lessons/search` remains the ordinary search endpoint.

Issue #219 preserves existing request fields, eligibility filters and
lifecycle semantics.

The request schema remains compatible, but the meaning of a non-empty `q`
intentionally broadens from a body-substring eligibility filter to a hybrid
retrieval query. Callers must not rely on the old guarantee that every returned
lesson literally contains `q` in its body.

Avoid changing the endpoint from its current result-list shape to a wrapper
solely to implement hybrid ranking.

Hybrid-search result fields should be additive and backward-compatible where
practical, for example optional ranking and explanation metadata.

Existing `/lessons/{id}/similar` and free-text similarity interfaces remain
specialized similarity capabilities and are not silently redefined as hybrid
search.

## Export compatibility

`POST /export/search` must reuse the maintained hybrid-search application
boundary for the equivalent query and filters.

Export must not contain an independent ranking implementation.

Existing export filtering semantics and `ids_in` behavior remain compatible
unless explicitly revised.

## GUI behavior

Browse is the primary ordinary hybrid-search surface.

The GUI should:

- keep one clear search action;
- retain power-user filters;
- avoid requiring similarity-engine knowledge;
- show concise `Why this result?` information on demand or in a compact form;
- preserve destructive-selection snapshot behavior when a new result set is
  loaded;
- distinguish lifecycle/freshness governance signals from relevance claims.

The existing specialized similarity UI may continue to serve explicit
similarity inspection.

## Failure and degradation behavior

Invalid authoritative or projection state follows existing fail-closed
contracts.

Optional semantic retrieval failure is different from invalid projection
authority.

When lexical/metadata search can execute safely but the optional semantic
artifact is missing or unavailable:

- search continues with the safe available signals;
- no hidden network fallback is introduced;
- the result must not falsely claim semantic contribution.

Unexpected semantic execution errors must not be silently converted into
fabricated scores. The implementation should distinguish a supported
unavailable/degraded state from unexpected operational failure.

## Local-first and privacy

Hybrid search remains fully local-first.

Issue #219 introduces no telemetry, remote embedding service, cloud index,
hidden upload or runtime network dependency.

Only local projection and local rebuildable model artifacts participate.

## Determinism and regression coverage

Tests must cover representative mixed-signal cases including:

- exact lexical match versus stronger semantic-only candidate;
- phrase/title/body lexical distinctions;
- lexical plus semantic reinforcement;
- metadata reinforcement;
- lifecycle filtering and explicit historical scope;
- freshness filtering;
- semantic model unavailable degradation;
- deterministic tie ordering;
- shuffled input producing stable order;
- bounded result limit;
- explanations matching actual ranking signals;
- no explanation claiming an unavailable signal.

## Non-goals

Issue #219 does not:

- change canonical authoring authority;
- make ranking a factual or truth judgment;
- introduce a remote/vector database;
- replace the projection-store contract;
- select SQLite as production projection backend;
- expose ML tuning in ordinary Browse;
- remove specialized similarity APIs;
- automatically mutate lifecycle or freshness metadata;
- add typed relationships as an initial ranking signal;
- introduce personalized or behavior-tracking ranking;
- require semantic artifacts for basic lexical search.
