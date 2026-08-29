# Native release reproducibility

The native desktop packages are release artifacts whose dependency identities
must remain reviewable across time.

## Dependency authority

Native releases use Python 3.12 and the committed
`requirements/native-release.txt` lock.

That file freezes both:

- the application runtime dependency graph embedded by PyInstaller; and
- the PyInstaller build toolchain itself.

The native release workflow must not use the broad `dev` optional dependency
set as build authority. Test, lint, type-checking, security-audit and developer
tools are deliberately outside the native release environment.

The checkout itself is installed only after the frozen environment exists, with
dependency resolution and isolated build-environment resolution disabled:

```text
python -m pip install -r requirements/native-release.txt
python -m pip install --no-build-isolation --no-deps -e .
```

This separation keeps normal runtime dependency declarations in
`pyproject.toml` independent from the exact dependency identities used to
produce a historical native release.

## Supported platforms

GitHub Actions builds native packages independently on Linux, macOS and
Windows.

Most locked dependency versions are shared across those platforms.
PyInstaller also has platform-specific dependencies, which remain explicitly
pinned behind environment markers in the lock.

The frontend remains independently frozen by `frontend/package-lock.json` and
is installed by the existing `npm ci` build path.

## Rebuilding a tag

To rebuild a historical release, use the source tree from that tag, Python
3.12, Node.js 22, its committed `frontend/package-lock.json`, and its committed
`requirements/native-release.txt`.

Do not regenerate the dependency graph from the open version ranges in
`pyproject.toml` before rebuilding. The lock committed in the release tag is
the native-build dependency authority.

## Observed reproducibility boundary

Issue #241 established a Linux baseline before changing the release path.

A broad `.[dev]` environment resolved 81 installed package entries. A minimal
runtime-plus-PyInstaller environment resolved 33 entries and produced a native
archive that passed the existing published-style smoke test.

Two clean Linux builds from the same commit and the same minimal environment
did not produce byte-identical outer archives.

The observed differences were structural rather than application-payload
drift:

- `base_library.zip` had a different member ordering between builds;
- after extraction, all 155 files in those two `base_library.zip` instances
  were byte-identical;
- the outer Linux tar archive also carried build-time filesystem metadata.

Therefore exact archive SHA-256 identity is not currently a truthful
cross-build reproducibility contract for the native package.

The maintained verification target is instead the strongest practical
normalized-content comparison: repeated builds must resolve from the same
dependency identities and their extracted payload content must match after
known container-order and timestamp metadata are excluded.

This limitation is explicit rather than silently treating differing native
archive hashes as dependency drift.

## Updating the lock

A lock update is a release-toolchain change and must be reviewed as such.

An update should:

1. resolve the intended graph for every supported release platform;
2. preserve platform markers where dependencies are platform-specific;
3. avoid unrelated dependency upgrades;
4. build and smoke-test the native packages;
5. repeat the reproducibility verification;
6. commit the reviewed lock alongside any required workflow change.
