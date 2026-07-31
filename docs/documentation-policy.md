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

This policy does not introduce GUI internationalization, CLI or API
localization, runtime language selection, automatic translation, a
documentation-site generator, or a translation-management platform.
