# Issue #262 — M4.2 qualification and M4.3 CI integration

Current status: **upstream v0.0.2 is distribution-qualified; M4.3 is implemented,
with full GitHub CI verification pending.** The earlier blocked candidate is
preserved below and in `historical_attempts` in the
[machine-readable record](issue-262-m4.2-qualification.json).

This is Python distribution and deterministic consumer qualification. It does
not qualify real Ollama inference, a provider/model's semantic quality, native
bundling of optional AI, or a complete LeLe release.

## Current upstream qualification

- Public repository: [gcomneno/giadaware-ai](https://github.com/gcomneno/giadaware-ai).
- Published experimental prerelease:
  [v0.0.2](https://github.com/gcomneno/giadaware-ai/releases/tag/v0.0.2).
- Source commit: `daa07b14bfd38ec049619881ea53546f44b2f27c`.
- Qualifying [GitHub Actions run 39229144633](https://github.com/gcomneno/giadaware-ai/actions/runs/39229144633):
  completed successfully at that exact commit.

The GitHub release/run APIs match the user-supplied identities. Local read-only
copies of the three canonical release assets also match these exact hashes:

| Canonical asset | SHA-256 |
| --- | --- |
| `giadaware_ai-0.0.2-py3-none-any.whl` | `9c0951244f1f43f0b27f6dc4ae3c69150d0c8588f6ac099cbe47ae11e21ed0a2` |
| `giadaware_ai-0.0.2.tar.gz` | `1d54759eb95cc17ddc8b2f01d95cca59ba509af20ba178cc6086df6ab6200d8f` |
| `provenance.json` | `62307c27e66dee144022f813f66f819413ba50f6dd9cde0442f52a5fb319e763` |

The hash-verified provenance records successful archive/license checks, both
isolated installed distributions/public APIs, sdist rebuild, and byte-identical
CI/rebuilt wheels. These are **upstream-recorded** checks, not builds repeated by
LeLe in M4.3. The provenance is evidence, not an independent cryptographic build
attestation. The release is mutable; the reviewed byte digest remains the trust
anchor.

M4.3 independently checked all three asset sizes and hashes, validated the real
canonical wheel with its acquisition validator, and inspected matching full
wheel/sdist license material: 11,924 bytes, SHA-256
`7c95b99f14be3e3d01dc0cb89ea7b89adee0b4ebacb4a8f8301b80b07a340f82`.
The original source candidate's license failure therefore remains historical;
it does not describe the selected published distribution.

Every `local-superseded-*` asset is excluded from canonical input selection.
The existing worktree `.venv` contains a different local `0.0.2` installation;
its version is not qualification evidence. The installed-provenance check
correctly rejects it. Inherited upstream `PYTHONPATH` also fails the shadowing
check; local qualifying runs use isolated Python mode.

## M4.3 implementation

Core remains Python `>=3.10`, without GiadaWare AI as a package dependency.
Optional AI requires Python `>=3.11`. CI selects core 3.10/3.12 and optional AI
3.11/3.12. Existing E2E and packaging jobs remain in place.

Default `python -m pytest -q` excludes `tests/optional_ai/` before import.
`python -m pytest -q --optional-ai tests/optional_ai` explicitly selects the
real optional API contracts. Dependency absence produces errors, not skips.
Provider-independent API, scope, disabled-provider and invalid-configuration
assertions remain in core. Assertions that backend construction never occurs
are strengthened to assert zero optional imports in core. All pre-existing test
function contracts remain represented. The old semantic `importorskip` and
availability `skipif` checks are removed; their assertions run in the optional
group. Optional tests forbid socket connections and DNS access, and inject fake
inference backends.

The stdlib-only [acquisition script](../scripts/acquire-optional-ai.py) downloads
one exact HTTPS release URL, with a timeout and size bound. It verifies SHA-256
**before parsing metadata or publishing the file**, checks exact name/version,
Python requirement and the qualified dev-only requirement, and refuses to
overwrite existing output. CI then installs the exact filename with
`--no-index --no-deps`, followed by installed name/version, canonical archive
hash in `direct_url.json`, and import-location checks. No PyPI fallback, optional
extra, inference service or runtime downloader is introduced.

Python 3.10 collection previously imported `tomllib` unconditionally in release
tests and scripts loaded by those tests. Those four imports now fall back to
`tomli`, declared only in the dev extra for Python <3.11. The core runtime gains
no dependency; native release policy remains Python 3.12. Existing packaging
entrypoints were inspected; destructive release cleanup was not used.

Existing M1–M4.2 runtime files and unrelated tests remain byte-identical to the
preflight snapshot. `ResolvedAssistantContext`, explicit provider opt-in,
canonical authority, transmission limits and fail-closed application behavior
are unchanged. This milestone changes CI, test organization, development-script
compatibility and evidence only.

## Observed M4.3 checks

| Gate | Observed result |
| --- | --- |
| Canonical cached wheel/sdist/provenance hashes | PASS |
| Real canonical wheel acquisition validator | PASS |
| Core wheel install / CLI help / API metadata / disabled provider, AI absent | PASS; temporary source copy and offline install; GUI assets not built |
| Core Python 3.12 collection, AI absent | PASS: 1,310 collected; one warning |
| Optional Python 3.12 collection, canonical wheel | PASS: 182 collected; one warning |
| Explicit optional collection with dependency absent | PASS for rejection: expected exit 2; four import errors; no dependency skips |
| Focused core Python 3.12 | PASS: 178 passed, zero skipped, one warning |
| Acquisition and packaging/CI-script contracts | PASS: 58 passed, zero skipped or warnings |
| Optional AI Python 3.12, canonical wheel | PASS: 182 passed, zero skipped, one warning |
| Selected optional AI Python 3.11, canonical wheel | PASS: 170 passed, zero skipped or warnings; 12 API cases not selected |
| Python 3.10.20 packaging-script fallback / acquisition rejection / syntax | PASS; smoke only, not full dependency installation or suite |
| Repository Ruff 0.15.22 | PASS: `ruff check .` |
| Mypy | PASS: 95 source files |
| CI validation | PASS: YAML parse; all 10 core/AI run blocks pass `bash -n` and ShellCheck; Python 3.10 script syntax |
| Live GitHub wheel acquisition | BLOCKED: DNS unavailable; exit 1; no output wheel/fallback |
| Broad core Python 3.12 | FAIL: 1,292 passed, 11 failed, seven skipped, six warnings |
| Full core 3.10 / full optional 3.11 matrix | NOT RUN: complete compatible dependency environments unavailable offline |
| GitHub Actions execution | NOT RUN: no commit/push/dispatch |
| Real inference, GUI build/E2E, full release packaging | NOT RUN: outside this Python/CI verification |

The final broad failures are all existing launcher tests that open local
sockets: this sandbox rejects socket creation with `EPERM`. Seven existing GUI
tests explicitly skip because packaged GUI assets are unbuilt. These are not
AI-dependency skips. Warnings include existing Starlette/Pydantic deprecations
and an intentionally duplicate archive member fixture. There were no retries
reported as flakes.

The local core/AI venvs reuse existing dependency files offline; they do not
prove a fresh dependency resolution on every matrix version. Python 3.11 uses
pure Python dependencies for the 170 selected non-API tests. Python 3.10 executes
the real TOML fallback with existing `tomli`, rather than relying only on syntax.

Direct API invocations initially hung on sandbox-blocked asyncio wakeups and
were interrupted. Temporary runners poll the selector and isolate synthetic
Vault/application state. Two earlier broad runs had additional runner-induced
failures (16 failures, then 29); their exact results and corrections remain in
the JSON record. The final runner redirects `Path.home` and XDG paths to
synthetic temporary locations without changing `$HOME`. No application changes
were made to accommodate the sandbox. An initial real-wheel validator rejected
the dev-only build requirement; its allowlist was corrected against the actual
canonical metadata and both real-wheel validation and focused tests passed.

The local live download attempt failed on DNS. Existing upstream canonical
copies were used only after byte verification; no local build, sibling-source
import or differently hashed wheel substitutes for the canonical distribution.
No real inference, commit, push, tag, PR, publication or destructive cleanup
occurred. The complete GitHub matrix and live acquisition must still execute on
a normal runner before M4.3 can be reported fully qualified.

## Final worktree review

Branch: `feat/262-ask-vault-giadaware-ai`. The following standard Git outputs
include the protected earlier work; `git diff --stat` excludes untracked files.
The JSON record also enumerates M4.3 changes relative to the preflight snapshot.
The removed semantic test path is relocated into `tests/optional_ai/`.

`git diff --stat`:

```text
 .github/workflows/ci.yml                       |  50 ++++-
 docs/ask-this-vault.md                         |  94 ++++++++-
 pyproject.toml                                 |   1 +
 scripts/build-native-app.py                    |   6 +-
 scripts/package-native-release.py              |   6 +-
 scripts/smoke-native-release.py                |   6 +-
 src/lele_manager/api/server.py                 |  60 ++++--
 src/lele_manager/application/ask_vault.py      |  23 ++-
 tests/conftest.py                              |  20 ++
 tests/test_api_ask_vault.py                    | 198 ++++++++++++++++++-
 tests/test_api_assistant_context.py            |   4 +-
 tests/test_ask_vault.py                        |  35 +++-
 tests/test_giadaware_ai_semantic_extraction.py | 260 -------------------------
 tests/test_release_packaging.py                |  27 ++-
 tests/test_semantic_composition.py             |  51 -----
 15 files changed, 493 insertions(+), 348 deletions(-)
```

`git diff --check`: **PASS**, exit 0, no output.

`git status --short`:

```text
 M .github/workflows/ci.yml
 M docs/ask-this-vault.md
 M pyproject.toml
 M scripts/build-native-app.py
 M scripts/package-native-release.py
 M scripts/smoke-native-release.py
 M src/lele_manager/api/server.py
 M src/lele_manager/application/ask_vault.py
 M tests/conftest.py
 M tests/test_api_ask_vault.py
 M tests/test_api_assistant_context.py
 M tests/test_ask_vault.py
 D tests/test_giadaware_ai_semantic_extraction.py
 M tests/test_release_packaging.py
 M tests/test_semantic_composition.py
?? docs/issue-262-m4.2-qualification.json
?? docs/issue-262-m4.2-qualification.md
?? scripts/acquire-optional-ai.py
?? src/lele_manager/adapters/giadaware_ai_ask_vault.py
?? src/lele_manager/ask_vault_composition.py
?? tests/optional_ai/
?? tests/test_api_assistant_context_coherence.py
?? tests/test_ask_vault_composition.py
?? tests/test_optional_ai_acquisition.py
```

## Preserved historical attempt

The following original M4.2 record describes the earlier candidate and its
blocked local qualification, **not the current published v0.0.2 status**.
Its JSON object is preserved unchanged under `historical_attempts`.

<details>
<summary>Original blocked M4.2 candidate record</summary>

# Issue #262 M4.2 — local Python wheel qualification

Status: **BLOCKED; candidate is not qualified; M4.3 is not ready.**

This record covers Python installations (pip, pipx, source-based CLI/GUI) only.
LeLe core remains Python `>=3.10`; the optional GiadaWare AI candidate declares
Python `>=3.11`. No application, packaging metadata, CI or native workflow changed.
This is distribution qualification, not real-provider or semantic qualification.

The machine-readable [qualification record](issue-262-m4.2-qualification.json)
contains the complete Git tree manifest, inspected source hashes, tool inventory,
protected Git state, artifact fields, and per-gate results.

## Source identity

- Repository: `https://github.com/gcomneno/giadaware-ai.git`.
- Candidate: `36a1bb751ec3851d3ceb0a38abe052747984ce5e`.
- Git tree: `617cd3ba7473c7501c9e07b82b02d3dcc1890ced`.
- Source-declared distribution: `giadaware-ai==0.0.1`.
- The commit exists locally. Inspection used its Git objects, not upstream HEAD.
  User selection is not an independently verified review attestation.

Both repositories' AGENTS.md and Git status/worktrees were read first. GiadaWare
AI was clean on `main` at `1c7429cbb20a257294bec7888349f9d164a21c2f`;
LeLe was on `feat/262-ask-vault-giadaware-ai` at
`a545e63` with pre-existing M1–M3 tracked/untracked work. That work is protected.

## Evidence, artifact locations and cleanup

These two records use LeLe's existing `docs/` technical/issue-document layout.
They are outside its release cleanup scope. LeLe's
[build-release-artifacts.sh](../scripts/build-release-artifacts.sh) removes
`build/`, `dist/` and `src/lele_manager.egg-info`; it was not invoked.

GiadaWare AI's documented canonical build-output root is its own `dist/`
(AGENTS.md installed-wheel command and `.github/workflows/ci.yml`). That root is
outside this session's writable roots. No write was attempted there and no
artifact was redirected to `/tmp`, a home directory or another output root.

A future writable run can use a unique, non-overwriting leaf below
`GiadaWare AI:dist/qualification/lele-manager-262-m4.2/<full-commit>/` to quarantine
candidate files away from root-level release distributables. This is a proposed
leaf within the documented root, not an existing qualification convention.
Nothing was created or promoted there. No upstream cleanup command was found;
existing artifacts must still be preserved.

## Results

| Gate | Result |
| --- | --- |
| Repository and source/tree identity | PASS |
| Static M2 API surface inspection | PASS |
| Evidence location in existing LeLe docs layout | PASS |
| Canonical artifact destination writable | BLOCKED |
| Available setuptools backend meets declared build requirement | PASS |
| Documented `python -m build` frontend available | BLOCKED |
| Clean isolated wheel/sdist build | BLOCKED |
| Artifact SHA-256 and integrity | BLOCKED |
| Separate installed-wheel metadata and API imports | BLOCKED |
| Source Apache-2.0 full license terms | FAIL |
| Wheel/sdist license inclusion | BLOCKED |
| Installed fake-backend adapter/composition smoke | BLOCKED |
| Independent optional-provider-disabled smoke | PASS |
| Focused LeLe service tests | PASS: 34 tests |
| Release promotion / M4.3 readiness | BLOCKED |

**No wheel or sdist was produced. Artifact filenames and checksums are null in
the JSON record. No installed-package gate passed.** Source declarations and
static API inspection do not substitute for installed distribution evidence.

The inspected Python was `3.12.3`. Available backend: `setuptools==84.0.0`,
which vendors `wheel==0.46.3`; these versions were observed, not used for a build.
The candidate requires `setuptools>=68`. The environment lacks `build` and
`pyproject-hooks`, so the documented frontend command cannot run offline as-is.
A direct backend invocation could avoid that frontend; artifact-path restrictions
still block this run. No network package installation was attempted.

Static inspection confirms root exports used by M2, including
`SynthesizeCapability` and the typed AI errors, plus
`giadaware_ai.backend.AIBackend.generate_json` with keyword-only
`system_prompt`, `user_prompt`, and `response_schema`. The candidate's
`OllamaBackend` accepts `model`, `base_url`, and `timeout`. Import compatibility
and constructor execution against an installed wheel remain unverified.

The source `LICENSE` is 708 bytes: an Apache-2.0 notice and link, with no full
license terms. Including that file unchanged would not supply the full terms
needed for redistribution. Correct the licensing upstream through review and
select the resulting new commit before qualifying redistribution. No upstream
license was changed. No tracked `NOTICE` exists; its absence alone is not claimed
as a violation, and any applicable notice obligations still require review.

## Independent disabled-provider verification

`.venv/bin/python -I -B -m pytest -q -p no:cacheprovider tests/test_ask_vault.py`
completed with **34 passed in 0.13s**, no failures or skips.

An additional isolated-mode source-only smoke ran with GiadaWare AI absent,
optional imports guarded, networking rejected by an audit hook, and synthetic
in-memory data. With the provider variable absent, both default configuration
and stray model/invalid timeout settings returned no synthesizer. Empty scope
returned `insufficient-support`; nonempty scope failed closed. There were zero
optional import attempts and zero network attempts. Synthesis was never enabled.

The existing installed-dependency adapter/composition test files were inspected
but not run. No Ollama inference, personal Vault access, broad test suite, build,
installation, commit, publication or cleanup was performed.

## Remaining prerequisites

1. Make the documented upstream artifact location writable in an authorized
   session; preserve existing contents and use a fresh quarantine leaf.
2. Supply the documented frontend from approved offline tools, or explicitly
   select the available pinned setuptools backend without dependency resolution.
3. Resolve the full Apache-2.0 license gap upstream and select a newly reviewed
   commit; do not patch the candidate inside a qualification build.
4. Export that exact clean Git tree, record source identity/tool pins, and build
   wheel and sdist without network resolution. Record real artifact hashes.
5. Install the wheel in a separate Python `>=3.11` environment without upstream
   editable installs, PYTHONPATH or sibling imports. Verify metadata, RECORD,
   source/package payload, license material, required exports and bounded
   fake-backend adapter/composition contracts. Recheck disabled behavior.
6. Promote only after every applicable gate passes. M4.3 CI integration remains
   unready until that evidence exists; no CI change is part of this record.

</details>
