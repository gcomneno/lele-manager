# Issue 219: Explainable hybrid search implementation plan

## Binding contract summary

Issue #219 introduces one maintained hybrid-search experience across lexical,
semantic and metadata signals.

The implementation is retrieval-only and advisory. It never authorizes
canonical mutation.

The ordinary user works with one search surface and maintained defaults rather
than choosing or tuning retrieval engines.

Key invariants:

- hybrid orchestration lives in an application boundary, not in the API
  controller or frontend;
- deterministic lexical matches receive protected precedence;
- semantic similarity complements lexical retrieval;
- missing optional semantic artifacts degrade safely to lexical/metadata
  ranking instead of making ordinary search unavailable;
- lifecycle remains primarily an eligibility policy and defaults to
  `active`;
- freshness remains advisory;
- metadata ranking contributions are bounded;
- result explanations come from the exact signals used by ranking;
- ordering is deterministic with a stable lesson-ID tie breaker;
- export reuses the same search boundary;
- typed relationships are outside initial #219 ranking scope.

## Current implementation baseline

At issue start:

- `POST /lessons/search` performs filtering and ordering directly in
  `api/server.py`;
- current text query behavior is case-insensitive substring filtering against
  body/text, which must intentionally change for true hybrid retrieval;
- default lifecycle scope is `active`;
- filters include topic, source, importance range, lifecycle and freshness;
- existing deterministic ordering is importance descending, creation time
  descending, lesson ID ascending;
- `POST /export/search` calls the search endpoint function and reuses its
  filters;
- semantic retrieval already has a separate similarity service/backend
  boundary;
- `core/ranking.py` currently configures similarity ranking only;
- Browse is the main GUI filtering/search surface;
- ordinary authoring already hides raw similarity tuning under the #189
  product contract.

## Proposed architecture

### Domain/core

Add hybrid-search ranking values that are backend-neutral and deterministic.

Expected concepts:

- maintained reason-code vocabulary;
- per-result signal evidence;
- deterministic ranking/tier/score representation;
- bounded maintained ranking configuration/constants;
- stable tie-break rules.

Do not put Pandas-specific types in the domain contract.

### Application

Add a dedicated hybrid-search service/workflow.

Responsibilities:

1. accept projection lesson records plus a user retrieval query/filter request;
2. apply maintained eligibility filters, excluding `q` from strict substring
   eligibility;
3. build the eligible candidate universe;
4. compute lexical evidence across maintained searchable fields;
5. obtain optional semantic evidence through a supplied similarity port;
6. combine the lexical and semantic candidate sets;
7. compute bounded metadata evidence;
8. compose deterministic ranking;
9. produce explanations from the same evidence;
10. apply final limit;
11. report supported semantic degradation without fabricating evidence.

The application service should not own HTTP errors or GUI localization.

### Similarity integration

Reuse the maintained similarity service/backend.

Provide only the bounded number of semantic candidates/evidence needed for
hybrid ranking.

Do not expose similarity tuning in ordinary search requests unless a separate
advanced compatibility decision is accepted.

Model missing/unavailable must have an explicit supported degradation path.

Unexpected operational/model corruption errors should remain distinguishable
from ordinary model absence.

### API

Refactor `POST /lessons/search` into request translation plus invocation of the
hybrid-search application boundary.

Preserve existing filters and list response compatibility.

Add optional result metadata sufficient for:

- rank;
- bounded hybrid relevance value if retained publicly;
- stable explanation reasons/evidence;
- semantic contribution/degradation indication where useful.

Do not expose raw weight tables unless needed for a maintained public contract.

### Export

Reuse the hybrid-search application boundary.

Preserve current export request inheritance, filtering and `ids_in` semantics.

Export ordering must match ordinary search for the same request before
post-search `ids_in` restriction.

### GUI

Update Browse to render maintained hybrid results.

Add concise EN/IT `Why this result?` UI without overwhelming the primary
workflow.

Keep current power-user filters.

Do not add ordinary controls for semantic `top_k`, `min_score`, backend or raw
weights.

### CLI

Existing CLI search should continue through `/lessons/search` and inherit
hybrid ranking automatically.

Only add output changes if ranking/explanation metadata materially improves the
maintained CLI contract.

## Proposed initial signal model

The exact numeric composition will be fixed during implementation tests, but
the following ordering constraints are binding.

### Query semantics

For #219, `q` becomes a retrieval query rather than the existing mandatory
body-substring filter.

The request field remains compatible, but result membership may broaden:
semantic or metadata-relevant lessons can be returned even when their body
does not literally contain `q`.

All explicit metadata/lifecycle/freshness constraints remain eligibility
filters.

With no `q`, the service performs deterministic filtered browse and does not
invoke semantic relevance for an empty query.

### Lexical

Strongest deterministic class:

- exact normalized title equals query;
- exact normalized phrase match.

Additional lexical evidence:

- title contains query;
- body/text contains query;
- token overlap where maintained.

A protected strong lexical result cannot be buried by a semantic-only result.

### Semantic

Optional bounded similarity score.

It may reinforce lexical evidence or retrieve conceptually related lessons that
lack direct lexical hits.

It never outranks protected strong lexical results solely by semantic score.

### Metadata

Candidate bounded signals:

- topic query/match;
- matching tags;
- matching source;
- importance;
- date/recency;
- lifecycle;
- freshness/review attention.

Filter constraints do not automatically become relevance bonuses.

### Tie breaking

Final ties are deterministic and eventually resolve by canonical lesson ID
ascending.

## Explainability vocabulary

Implementation should select and test a stable bounded vocabulary, likely
covering concepts such as:

- `exact-title-match`;
- `exact-phrase-match`;
- `title-match`;
- `text-match`;
- `topic-match`;
- `tag-match`;
- `source-match`;
- `semantic-similarity`;
- `importance`;
- `lifecycle-active`;
- `lifecycle-review-needed`;
- `freshness-review-needed`.

This list is proposed, not final, until scoring semantics are implemented
together with their tests.

Reason payloads should contain only bounded user-useful values, such as tag
count/names or rounded similarity value where applicable.

## Ordered implementation phases

1. Contract and domain values

   Add hybrid reason/evidence/result and ranking configuration primitives.
   Fix deterministic ordering invariants and lexical-protection rules in tests.

2. Lexical and metadata ranker

   Implement pure deterministic ranking without semantic dependency.
   Preserve existing filters and lifecycle defaults.

3. Semantic integration

   Add optional semantic evidence through a narrow application port.
   Implement safe model-unavailable degradation and explicit failure semantics.

4. Application search workflow

   Compose filters, signals, ranking, explanations and limits behind one
   service.

5. API and export integration

   Route `/lessons/search` and `/export/search` through the application
   boundary while preserving compatibility.

6. GUI explainability

   Update Browse and EN/IT localization with concise `Why this result?`
   rendering.

7. CLI/documentation compatibility

   Verify CLI behavior and update user documentation where the observable
   search contract changed.

8. Generated GUI and final gates

   Rebuild packaged static GUI, inspect generated changes and execute all
   proportional repository gates.

## Test matrix

### Domain/ranking

- lexical normalization is deterministic;
- exact title match is protected;
- exact phrase match is protected;
- semantic-only candidate cannot bury protected lexical match;
- metadata-only boosts are bounded;
- tie order ends in stable ID ordering;
- shuffled input yields identical ranked IDs and explanations;
- unknown reason codes fail explicitly where validation is maintained.

### Filtering

- lifecycle omission remains active-only;
- explicit lifecycle scopes remain composable;
- empty lifecycle scope remains empty;
- topic filter composes with hybrid ranking;
- source filter composes with hybrid ranking;
- importance range composes with hybrid ranking;
- freshness filter composes with hybrid ranking;
- limit applies after ranking.

### Semantic

- semantic score reinforces an eligible lexical result;
- semantic retrieval can surface conceptually related non-lexical results;
- semantic model unavailable degrades to lexical/metadata search;
- degradation never invents semantic explanation;
- unexpected similarity operational failure remains visible according to the
  maintained failure contract;
- no hidden network fallback occurs.

### Explainability

- each returned reason corresponds to an actual ranking signal;
- no score-affecting maintained signal is silently represented by unrelated
  wording;
- exact title/phrase reasons are distinguishable;
- tag explanation contains bounded deterministic values;
- semantic explanation contains a bounded display value if exposed;
- lifecycle/freshness wording does not imply truth.

### API

- current request payload remains accepted;
- non-empty `q` is verified as hybrid retrieval rather than strict body
  substring filtering;
- semantic-only eligible results may appear without literal body containment;
- explicit filters still constrain eligibility before ranking;
- current response lesson fields remain present;
- additive ranking/explanation fields validate;
- representative mixed-signal ordering is stable;
- missing semantic model does not make ordinary search return 503;
- malformed projection still follows existing fail-closed behavior.

### Export

- same search request produces same pre-filter ranking as API;
- `ids_in` remains a post-search restriction;
- export remains deterministic.

### GUI/E2E

- ordinary Browse search uses maintained defaults;
- no raw similarity tuning appears in normal Browse;
- `Why this result?` is available;
- EN and IT wording are maintained;
- exact-match result visibly remains ahead of semantic-only alternative;
- explicit deprecated/archived scope remains available;
- changing query/result set still clears destructive selection.

### Compatibility

- specialized similarity endpoints preserve existing semantics;
- similarity service equivalence tests remain valid;
- GET `/lessons` behavior remains unchanged unless explicitly required;
- CLI search remains compatible through the API contract.

## Validation gates

Focused during implementation:

- new hybrid-search domain/application tests;
- existing `tests/test_search_api.py`;
- existing `tests/test_search_api_hardening_and_ordering.py`;
- existing `tests/test_ranking_config.py`;
- existing similarity service/backend tests;
- freshness/lifecycle search tests;
- export-search tests;
- relevant Browse Playwright spec.

Before final handoff:

- `./scripts/build-gui.sh`;
- inspect generated static diff;
- `ruff check .`;
- `mypy src/lele_manager`;
- `pytest -q`;
- frontend checks;
- relevant/full Playwright according to changed surface;
- `pip-audit`;
- `bandit -r src -x tests -s B101`;
- separate `npm audit --omit=dev` observation without implicit fix;
- `git diff --check`;
- final diff/status inspection.

## Explicit non-goals

Do not:

- add cloud/vector search;
- add remote embeddings;
- make similarity mandatory for basic search;
- move canonical authority into a search index;
- add automatic canonical mutation;
- expose raw ranking weights to ordinary users;
- add relationship ranking in initial #219;
- replace the projection backend;
- change snapshot contracts;
- silently change lifecycle;
- claim freshness means factual staleness;
- duplicate ranking logic across API, export and GUI;
- make the frontend compute relevance.

## Definition of done

Issue #219 is complete when:

- one maintained search surface combines lexical, semantic and metadata
  signals;
- exact/direct lexical matches have explicit protected behavior;
- semantic retrieval is complementary and safely degradable;
- filters and lifecycle semantics remain compatible and composable;
- ranking is deterministic and bounded;
- each result can explain why it ranked where it did using maintained
  user-facing reasons;
- Browse exposes that explanation without ML tuning burden;
- API/export share one application ranking contract;
- focused and broad verification pass;
- documentation accurately describes the implemented behavior.
