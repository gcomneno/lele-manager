# PyPI environment deployment policy

The GitHub environment named `pypi` is part of LeLe Manager's package-publishing
trust boundary.

PyPI publication uses GitHub OIDC trusted publishing. The repository does not
use a long-lived PyPI password or API token for this workflow.

## Release control plane

The PyPI publication workflow is manually dispatched.

Only a workflow run whose GitHub execution ref is the repository's `main`
branch is allowed to enter the `pypi` environment.

The environment is configured with:

- custom deployment branch policies enabled;
- exactly one allowed deployment ref: branch `main`;
- administrator bypass disabled;
- no required reviewers.

This means an arbitrary feature branch cannot satisfy the environment
deployment gate, including when the workflow file itself exists on that branch.

## Package source identity

The branch allowed to enter the environment is not the package source identity.

The workflow receives an explicit `version_tag` input, checks out that existing
release tag, and verifies that the tag version matches the package version in
`pyproject.toml` before building artifacts.

The maintained trust chain is therefore:

```text
manual workflow dispatch from main
  -> pypi environment permits main
    -> checkout explicit existing version_tag
      -> verify tag/package version identity
        -> build artifacts from that tag
          -> publish through OIDC trusted publishing
```

The environment deployment policy evaluates the workflow run ref. The
`version_tag` input remains an independent release-artifact identity check.

## Reviewer decision

Required reviewers are intentionally not configured.

LeLe Manager currently operates with a single maintainer. Requiring that same
maintainer as the sole deployment reviewer would not create meaningful
separation of authority, while preventing self-review would make the release
path unusable.

If release authority later becomes shared across multiple maintainers, this
decision should be reviewed.

## Administrator bypass

Administrator bypass is disabled for the `pypi` environment.

The deployment branch policy therefore remains an actual gate for repository
administrators as well as ordinary workflow runs.

## Authentication and permissions

The publication job keeps least-privilege permissions:

- `contents: read`
- `id-token: write`

OIDC trusted publishing remains the only publishing authentication mechanism.

No long-lived PyPI credential is introduced by this policy.

## Verification

The environment should report:

- `can_admins_bypass: false`;
- a `branch_policy` protection rule;
- `protected_branches: false`;
- `custom_branch_policies: true`;
- exactly one deployment branch policy:
  - name: `main`
  - type: `branch`

A production package must not be published solely to test this policy.
