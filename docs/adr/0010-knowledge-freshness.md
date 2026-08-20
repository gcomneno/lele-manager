# ADR 0010: Explainable knowledge freshness and review attention

## Decision

LeLe Manager exposes freshness as derived, explainable review prioritization.

Freshness is advisory state. It may tell a user that a canonical LeLe deserves
attention, but it never declares that the knowledge is false, obsolete, or
incorrect and never mutates canonical Markdown merely because time passed or a
derived signal exists.

This contract deliberately keeps two concepts separate:

- canonical lifecycle `review-needed` is explicit maintained lesson state;
- derived `freshness.review_needed` is computed review attention.

A lesson can therefore remain canonically `active` while its derived freshness
assessment recommends review.

## Canonical review metadata

Canonical Markdown may contain two optional maintained fields:

    reviewed_at: 2026-08-20
    review_interval_days: 180

`reviewed_at` records the date of the last explicitly confirmed human review.
It uses the exact `YYYY-MM-DD` calendar-date format.

`review_interval_days` is an optional per-LeLe review interval. It must be an
integer from 1 through 3650 inclusive.

When no per-LeLe interval exists, the maintained product default is 365 days.

The absence of either field remains valid canonical state and does not require
migration of existing Vaults.

Vault Doctor and canonical import validate these maintained fields with the same
domain rules used by freshness calculation.

## Temporal baseline

Freshness age uses one baseline:

1. `reviewed_at`, when present;
2. otherwise the parseable canonical lesson `date`.

The legacy `date` field predates this decision and may contain free-form values
in older data. If it cannot be parsed as an ISO calendar date, LeLe Manager does
not invent an age signal.

Future baselines are clamped to zero elapsed days rather than producing a
negative age.

A lesson becomes age-due when elapsed days are greater than or equal to its
effective review interval.

## Relation-based freshness

Typed relationships from ADR 0009 can contribute derived review attention, but
only when the required temporal evidence exists.

Incoming `corrects` and `extends` relationships signal freshness only when the
source lesson has a parseable canonical lesson date that is strictly later than
the target lesson's freshness baseline.

Therefore:

- a same-date relation is not considered newer;
- an older source is not considered newer;
- a source with no parseable date produces no newer-knowledge claim;
- after an explicit review whose `reviewed_at` is later than the source lesson
  date, that relation no longer keeps the target in review attention.

The source lesson's `reviewed_at` is not used to establish relationship
newness. The source lesson's canonical lesson date is the maintained evidence.

Canonical `superseded_by` remains a persistent semantic signal because it names
an authoritative replacement. It does not depend on relative dates.

`contradicts` is intentionally excluded from freshness. Contradiction review is
owned by the separate contradiction-review gate and must not be silently
implemented here.

## Lifecycle interaction

Canonical lifecycle `review-needed` always contributes an explicit freshness
reason.

Canonical `deprecated` and `archived` lessons suppress derived freshness noise.
They remain directly addressable, but they do not add age, relationship, or
supersession review-attention counts.

Derived freshness never changes lifecycle automatically.

## Explicit review action

Lesson Detail provides an explicit `Record review` action for canonical lessons.

The action requires the exact canonical revision fingerprint loaded by Detail.
It therefore participates in the optimistic-concurrency contract from ADR 0008
and fails closed when the canonical lesson changed in the meantime.

A successful explicit review:

- records `reviewed_at` as the current UTC calendar date;
- changes canonical lifecycle from `review-needed` to `active`;
- leaves `active`, `deprecated`, and `archived` lifecycle unchanged;
- preserves body, metadata, typed relationships, supersession, and the explicit
  review interval;
- records the change through the maintained revision-aware authoring boundary.

The action does not revive deprecated or archived knowledge.

Repeating the action on the same date when it would produce identical canonical
state is a no-op and does not manufacture revision history.

## Canonical success and derived refresh

Canonical review mutation and derived reconciliation remain separate outcomes.

If canonical Markdown and revision history are successfully written but
projection refresh fails, canonical success remains authoritative. The API and
GUI report partial success explicitly and do not roll back canonical review
metadata merely because derived state could not be refreshed.

A later reconciliation may rebuild projection/search state without repeating
the canonical review action.

## Query and UI surfaces

Freshness is surfaced without turning normal knowledge browsing into a warning
dashboard.

Dashboard reports a bounded count of lessons with derived review attention and
links to Browse.

Browse provides a separate `Review attention` filter. It is independent from
the canonical Lifecycle selector so users can distinguish explicit lifecycle
state from derived freshness.

Detail explains the current assessment, including effective interval, age when
available, readable reason codes, and related lesson IDs. It also owns the
explicit `Record review` action.

Editor exposes the optional per-LeLe `review_interval_days` override. Clearing
the field removes the override and restores the 365-day derived default.

Editor deliberately does not expose manual editing of `reviewed_at`; recording
that a review actually happened remains a distinct explicit action.

Search and Dashboard calculate relationship signals against the complete
current projection before applying result filters, so an incoming relation is
not lost merely because its source would not match the current Browse query.

## Explainability

The maintained freshness reasons are:

- explicit canonical lifecycle `review-needed`;
- review interval overdue;
- newer incoming `corrects`;
- newer incoming `extends`;
- canonical supersession.

Reason ordering is deterministic.

The assessment exposes the baseline date, elapsed age when available, effective
review interval, boolean review attention, and readable reasons. Thresholds and
bounds are named maintained constants rather than opaque scoring weights.

There is no hidden ML freshness score.

## Non-goals

This decision does not:

- perform factual verification;
- decide whether knowledge is true or false;
- implement contradiction-review workflow;
- automatically rewrite or deprecate old lessons;
- automatically change lifecycle from age or relations;
- infer review completion from reading, searching, editing, or similarity use;
- make `contradicts` a freshness reason;
- introduce remote services, telemetry, accounts, or cloud state;
- implement Context Packs, RAG, or a Vault chatbot.
