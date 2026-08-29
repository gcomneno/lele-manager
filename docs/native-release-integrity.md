# Native release integrity and provenance

LeLe Manager native GitHub Releases use several independent integrity
guarantees. They complement one another and should not be treated as
interchangeable.

## Four distinct guarantees

### 1. Release immutability

GitHub Immutable Releases are enabled for the repository.

For releases published after that repository setting was enabled, GitHub
protects the published release, its tag and its assets according to the
platform's immutable-release contract.

Historical releases are not retroactively claimed immutable. In particular,
the audited `v1.11.1` release was published before this remediation and was
observed with:

```text
immutable: false
```

Do not mutate an existing production release merely to test historical
behavior.

### 2. Release asset digest

GitHub records a SHA-256 digest for each uploaded release asset.

The digest answers:

> Are these downloaded bytes the bytes GitHub recorded for this release asset?

It does not by itself prove how those bytes were built.

### 3. Reproducibility

Native build reproducibility is maintained separately by
`docs/native-release-reproducibility.md` and
`scripts/verify-native-reproducibility.py`.

That contract compares repeated native builds at the strongest practical
normalized-content level currently supported by the PyInstaller packaging
boundary.

Reproducibility does not replace release immutability or provenance.

### 4. Build provenance

Each native archive produced by the `native-packages` job is explicitly
attested with GitHub artifact attestations.

The attested subject is the exact file under:

```text
dist/release/*
```

that is subsequently uploaded as the native workflow artifact and later
published as the GitHub Release asset.

The attestation therefore binds the downloadable native archive to its GitHub
Actions build identity and source context.

Attestation permissions are intentionally scoped only to the native build job:

```text
contents: read
id-token: write
attestations: write
```

The GitHub Release publication job does not receive attestation or OIDC write
permissions.

## User verification

For a future immutable release, users can independently verify different
properties.

Verify the release's immutable-release state:

```text
gh release verify <tag> --repo gcomneno/lele-manager
```

Verify a downloaded release asset against GitHub's recorded release asset:

```text
gh release verify-asset <tag> <path-to-downloaded-asset> \
  --repo gcomneno/lele-manager
```

Verify the GitHub artifact attestation for the downloaded native archive:

```text
gh attestation verify <path-to-downloaded-asset> \
  --repo gcomneno/lele-manager
```

These checks answer different questions:

- release verification covers GitHub's immutable-release state;
- release-asset verification covers the recorded asset digest;
- attestation verification covers provenance;
- the repository's reproducibility verifier covers repeated-build content
  stability.

## First release after remediation

The first native release published after this change should be checked
explicitly before considering the remediation fully exercised in production:

1. GitHub reports the release as immutable;
2. ordinary release edit or asset replacement paths are blocked according to
   GitHub's immutable-release contract;
3. each native release asset has its expected SHA-256 digest;
4. each downloaded native archive verifies against its GitHub attestation;
5. existing install and published-style native smoke behavior remains valid.

This first-release verification is operational evidence and must not be
retroactively inferred from historical releases.
