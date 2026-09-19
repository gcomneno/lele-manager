# Documentation language policy

[English](documentation-policy.md) | [Italiano](it/documentation-policy.md)

## Canonical language

English is the canonical and default language for maintained public documentation.
Italian is an officially maintained translation for the document families listed
as bilingual below.

When English and Italian wording diverge, the English document is the source of
truth. A translation must preserve requirements, examples, warnings, limitations,
and technical meaning; it must not be a shortened summary.

Commands, CLI options, HTTP endpoints, Python symbols, environment variables,
paths, filenames, and code snippets are never translated.

## Product presentation

English is also the canonical and default maintained source for current public
product presentation unless a surface explicitly maintains deterministic
localized catalogs.

Language selection affects presentation only. It must not change domain rules,
authorization, mutations, structured results, exit codes, validation, workflow
behavior, identifiers, routes, fingerprints, or machine-readable contracts.

The GUI currently maintains deterministic English and Italian catalogs. English
is the source contract; Italian is a derived presentation catalog. Unsupported
GUI locales fall back to English.

The CLI and API do not currently expose a language selector and may retain
legacy presentation text. New maintained presentation text uses canonical
English unless that surface explicitly adopts deterministic localized catalogs.
A selector is appropriate only when that surface maintains real presentation
catalogs with equivalent language semantics.

Static strings should use deterministic catalogs or source resources. Dynamic
human-readable content may use a shared provider-independent GiadaWare AI
Translation capability only when runtime translation is genuinely required.
Such translation must preserve meaning, must not summarize, rewrite, enrich,
materially simplify, or correct domain content, and must fall back to canonical
English on failure. Dynamic translation is optional integration behavior, not a
core LeLe Manager runtime dependency.

User-authored knowledge, canonical Markdown, structured API/CLI results, JSON
keys, error codes, enum values, routes, IDs, fingerprints, paths, and other
machine-readable contracts are not translated.

## Naming and navigation

- Root documents use `.it.md` for their Italian mirror:
  `README.md` / `README.it.md`, `ROADMAP.md` / `ROADMAP.it.md`, and
  `CONTRIBUTING.md` / `CONTRIBUTING.it.md`.
- Canonical documents under `docs/` are English.
- Maintained Italian translations under `docs/it/` preserve the same filename
  and relative directory structure.
- Every maintained pair starts with visible reciprocal `English` and `Italiano`
  links.
- Internal links should stay in the reader's language when a mirror exists.
  Otherwise they may point to the English canonical source.

## Inventory and coverage

| Path or document family | Language before #135 | Policy after #135 | Rationale |
|---|---|---|---|
| `README.md` | Predominantly Italian | Bilingual and maintained; English canonical | Primary user onboarding and product reference |
| `README.it.md` | Not present | Bilingual and maintained; Italian mirror | Official Italian entry point |
| `ROADMAP.md` | Predominantly Italian | Bilingual and maintained; English canonical | Public project direction and status |
| `ROADMAP.it.md` | Not present | Bilingual and maintained; Italian mirror | Official Italian roadmap |
| `CONTRIBUTING.md` | Predominantly Italian | Bilingual and maintained; English canonical | Public contributor workflow |
| `CONTRIBUTING.it.md` | Not present | Bilingual and maintained; Italian mirror | Official Italian contributor guide |
| `CHANGELOG.md` | Mixed Italian and English | English-only technical/release source | Historical entries remain unchanged; new entries use English |
| `RELEASE_NOTES.md` | English | Historical/archive document, English-only | Existing historical release notes are not maintained as a bilingual manual |
| `frontend/README.md` | English | Generated artifact | Upstream Vite/Svelte scaffold content; replace separately if project-specific guidance is needed |
| `.github/pull_request_template.md` | Predominantly Italian | English-only contributor metadata | Repository-wide default workflow; includes bilingual-doc synchronization checks |
| `docs/documentation-policy.md` | Not present | Bilingual and maintained; English canonical | Defines the repository language contract |
| `docs/it/documentation-policy.md` | Not present | Bilingual and maintained; Italian mirror | Official Italian policy |
| `docs/projection-store.md` | English | Bilingual and maintained; English canonical | Current contributor-facing storage contract |
| `docs/it/projection-store.md` | Not present | Bilingual and maintained; Italian mirror | Official Italian storage-contract translation |
| `docs/brand-design-system.md` | Not present | Bilingual and maintained; English canonical | Maintained product brand and design-system contract |
| `docs/it/brand-design-system.md` | Not present | Bilingual and maintained; Italian mirror | Official Italian brand and design-system translation |
| `docs/pro-commercial-readiness.md` | Not present | Bilingual and maintained; English canonical | Maintained Pro product readiness and positioning contract |
| `docs/pypi-environment-policy.md` | Not present | English-only technical source | Maintained PyPI deployment-security and release-governance contract |
| `docs/native-release-reproducibility.md` | Not present | English-only technical source | Maintained native-release dependency and reproducibility contract |
| `docs/native-release-integrity.md` | Not present | English-only technical source | Maintained native-release immutability, digest and provenance contract |
| `docs/main-branch-protection.md` | Not present | English-only technical source | Maintained main-branch governance and required-check contract |
| `docs/it/pro-commercial-readiness.md` | Not present | Bilingual and maintained; Italian mirror | Official Italian Pro product readiness translation |
| `docs/adr/0001-storage-backend.md` | Predominantly Italian | English-only technical source | ADRs are canonical technical records maintained in English |
| `docs/gui-design.md` | Predominantly Italian | Historical/archive document | Completed GUI design record; retained in its original language |
| `docs/phase-4-issue.md` | Predominantly Italian | Historical/archive document | Completed local tracking document; no ongoing translation obligation |

Contributor-facing issue forms are not Markdown, but their language also affects
the repository experience:

| Path | Policy after #135 |
|---|---|
| `.github/ISSUE_TEMPLATE/bug_report.yml` | English-only contributor metadata |
| `.github/ISSUE_TEMPLATE/feature_request.yml` | English-only contributor metadata |

Every exclusion is deliberate: generated scaffolds, historical records, and
English-only technical sources do not create an Italian synchronization
obligation.

## Synchronization workflow

A pull request that changes a bilingual canonical document must:

1. evaluate whether the Italian mirror requires the same change;
2. update both files in the same pull request when technical meaning changes;
3. preserve reciprocal language links;
4. keep technical tokens and snippets unchanged;
5. run the documentation checks.

Run the focused checks with:

```bash
pytest tests/test_documentation.py
```

The checks verify required pairs, reciprocal language selectors, same-language
root navigation, and relative links in maintained bilingual documents. They do
not attempt machine translation or automatic semantic comparison; semantic
parity remains a reviewer responsibility.

## ADR policy

Architecture Decision Records are English-only canonical technical records.
Existing ADR content is migrated to English without changing the recorded
decision. New ADRs should be written in English and do not require Italian
mirrors unless this policy is changed explicitly.

## Changelog policy

`CHANGELOG.md` is the canonical English release history. Existing mixed-language
historical entries are retained to avoid rewriting release history. New entries
must use English.

## Non-goals

This policy does not introduce CLI or API runtime language selection, automatic
translation, a documentation-site generator, or a translation-management
platform. It also does not make GiadaWare AI a core runtime, network, cloud,
account, telemetry, or provider dependency of LeLe Manager.

Repository-specific exceptions may remain for legal, externally imposed,
educational, upstream, archival, generated, historical, or explicitly documented
compatibility reasons.
