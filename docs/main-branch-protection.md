# Main branch protection

The default branch `main` is an authority boundary for LeLe Manager source and
release development.

GitHub repository ruleset `main-protection` is the platform enforcement for
that boundary.

## Required path to main

Ordinary source changes must reach `main` through a pull request.

Direct ordinary pushes are not an accepted development path.

The active ruleset targets the repository default branch and has no bypass
actors.

## Required checks

A pull request must satisfy these GitHub Actions checks before merge:

- `test`
- `e2e`
- `packaging-smoke`
- `security-scan`

Each required check is bound to the GitHub Actions app identity observed for
the repository.

The status-check policy is intentionally non-strict with respect to the latest
base-branch commit. A concurrent merge therefore does not automatically require
rerunning an otherwise valid pull request solely because `main` advanced.

## Pull-request review policy

The repository is currently maintained by a single maintainer.

The ruleset therefore requires the pull-request path but sets:

```text
required_approving_review_count: 0
```

A mandatory self-approval requirement would deadlock normal maintenance without
adding an independent reviewer.

Code-owner review, last-push approval, stale-review dismissal and mandatory
review-thread resolution are not currently required.

This is a deliberate single-maintainer operating choice, not an assertion that
independent review has no value. The policy should be reconsidered if the
maintainer model changes.

## History protection

The existing protections remain enabled:

- branch deletion is blocked;
- non-fast-forward updates are blocked.

No bypass actor is configured, and the repository owner does not have a ruleset
bypass path for ordinary development.

Signed commits and linear-history enforcement are not currently required.
They were not added because the issue goal is to enforce the already-established
PR-and-CI development path without introducing unrelated operational controls.

## Release compatibility

Release workflows do not require source changes to bypass `main`.

Tag-triggered and publication workflows operate from already-accepted source
history and do not need a broad ruleset bypass actor.

Repository protection therefore remains separate from:

- PyPI environment deployment policy;
- immutable GitHub Releases;
- artifact provenance;
- native build reproducibility.

## Verification

The maintained protection contract should be checked by observing all of the
following:

1. the effective `main-protection` ruleset contains `pull_request`,
   `required_status_checks`, `deletion` and `non_fast_forward`;
2. no bypass actor is configured;
3. a pull request cannot merge while any required check is pending or failing;
4. a pull request with all required checks passing can follow the normal merge
   path;
5. direct ordinary updates to `main` are rejected by GitHub policy.

Required check names are part of this operational contract. If CI job names are
changed, update the ruleset and this document together to avoid deadlocking
future merges.
