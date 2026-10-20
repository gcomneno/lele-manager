# Issue #264: registered Vault isolation audit

## Authority and audit inventory

This audit follows ADRs [0003](adr/0003-multi-vault-registry.md),
[0004](adr/0004-vault-snapshots.md), [0005](adr/0005-vault-transfer-merge.md),
[0006](adr/0006-vault-danger-zone.md), and the maintained
[Ask-this-Vault contract](ask-this-vault.md). Status describes the implementation
before #264; the last column records the hardening or retained boundary.

| Boundary | Audit status | Evidence and disposition |
| --- | --- | --- |
| Stable registered UUID and Markdown root | ALREADY_ENFORCED / GAP | `vault_registry.py` generates immutable UUIDs and absolute resolved roots. Loading previously resolved stored paths again, accepting redirected/relative authority and differently spelled duplicate UUIDs. Now reject unsafe/noncanonical roots, duplicate JSON fields and equivalent UUID identities. Preserve each existing unique UUID's spelling and artifact namespace. |
| Registry precedence | ALREADY_ENFORCED | `bootstrap()`, `core/paths.py`, ADR 0003: `LELE_VAULT_DIR` selects only the bootstrap source. Existing active ID wins; deprecated file overrides are not managed runtime authorities. Malformed registries never fall back to environment authority. |
| Activation and operation coherence | ALREADY_ENFORCED / GAP | API activation imports without frontmatter writes before selecting the target. Most request paths already capture one context. CLI TritaLeLe approval resolved a second context for candidates; now all approval dependencies use the first context. Activation also validates target artifact ownership. Failed activation retains the previous selection. |
| Canonical root overlap/nesting | ALREADY_ENFORCED / GAP | Registration and load already reject equal/nested registered roots. `create()` performed mkdir before checking conflicts; validation now precedes mkdir under the registry mutation lock. Canonical/state namespace overlap was unchecked; now rejected without moving anything. |
| Canonical enumeration and retrieval | GAP | Importer followed linked Markdown files; tree recursion followed directory links; ordinary ID resolution could read linked content. A common complete preflight now rejects symlinks, hard links and special nodes, including linked ancestors. Canonical reads and the projection import use this boundary. Enumeration remains deterministic and includes case-insensitive `.md` files. |
| Projection, search and external retrieval | ALREADY_ENFORCED / GAP | Projections are UUID scoped; hybrid search captures a context. External retrieval reads one active projection. A redirected projection file/directory could expose another scope. Context construction validates scoped trees; projection reads/publication/legacy append also check ownership at access. Ordinary API path resolution reports registry failure through the existing 503 mapping. |
| Ask-this-Vault scope | ALREADY_ENFORCED / GAP | Explicit IDs, search and Context Pack resolution already share one canonical scope and restrict citations. Canonical link traversal could supply foreign grounding. The common canonical read boundary now rejects it before provider composition. Identical lesson IDs in different Vaults remain valid and resolve within the captured root. |
| Authoring and deletion | ALREADY_ENFORCED / GAP | Existing code checks containment and rejects ambiguous destructive IDs. Normal authoring could follow root aliases or modify a hard-linked inode. Destination checks now precede mkdir/writes, refuse linked ancestors/targets and traversal; canonical reading/deletion translates unsafe namespace failures to existing domain errors. |
| Candidates, import and approval | ALREADY_ENFORCED / GAP | Staging is UUID scoped; API dependencies already share a request context; approval is collision-safe with separate canonical/refresh outcomes. CLI approval now captures one context, staging access checks ownership, and approval publication/verification uses the shared canonical checks. PKPS and raw-source input are explicit external inputs staged in the selected scope. |
| Cache and ML/model artifacts | ALREADY_ENFORCED / GAP | Similarity cache keys already include UUID, artifact paths and mtimes. Model files are UUID scoped. A substituted model/scope could redirect reads/writes. Scoped context validation and model access now reject links before joblib serialization/deserialization. |
| Snapshot and restore | ALREADY_ENFORCED / GAP | Explicit registered destination, plan digests, archive validation, safe mutation and partial-success results already exist. Snapshot canonical checks now also reject hard-linked Markdown and unsafe root ancestors; scoped checks also reject unsafe ancestors and hard links. Restore does not change selection or identity. |
| Transfer and Danger Zone | ALREADY_ENFORCED | Explicit registered contexts, preview-bound execution, source verification, bounded deletion and per-scope derived refresh are already maintained. They inherit the strengthened registry/snapshot filesystem checks. No new transfer or destructive operation is introduced. |
| Shared workflow documents | ALREADY_ENFORCED | Context Packs and duplicate decisions share application documents but normal operations filter by registered UUID. Revision history, contradiction and factual-review artifacts live in the selected scoped data directory. Scoped-tree checks prevent directory/file redirection. Physical per-document separation of global stores is not an existing guarantee. |
| Snapshot coverage of later editorial features | AMBIGUOUS | Snapshot schema 1 explicitly covers Markdown, candidates and scoped duplicate decisions. Revision history, Context Packs and later review state are not added by this isolation issue. Expanding portable backup coverage requires a separate format/lifecycle decision; current UUID ownership is unchanged. |
| Startup and managed compatibility helpers | ALREADY_ENFORCED | `launcher.prepare_runtime()` captures one context before creating runtime directories. `core/storage.py` defaults through managed `lessons_path()`. Runtime transparency remains read-only and surfaces invalid registry authority. Module-level API path overrides are internal test seams. These paths inherit strengthened registry/artifact checks. |
| Standalone file tools | OUT_OF_SCOPE / AMBIGUOUS | Standalone topic training, suggestion, CSV, polling watcher and read-only Doctor commands retain their established file-oriented inputs/defaults. Some dataset/model defaults remain historical global paths; they are not authorities for registered-Vault API operations. Making these tools' defaults active-Vault-aware is a separate compatibility/authority decision, not a silent migration in #264. Explicit `--db`/input/output modes remain file-oriented. |
| Process security | OUT_OF_SCOPE | Authentication between local OS users, arbitrary filesystem edits, bind mounts, malicious joblib payloads, cross-process transactions and OS sandboxing are not supplied by the registry. |

## Root and filesystem policy

Registered canonical roots must be pairwise disjoint: equality, ancestors and
descendants are all forbidden, regardless of display name. Registration resolves
an explicitly supplied alias once, preserving ADR 0003. Thereafter the stored
absolute root must remain canonical; replacing it or an ancestor with a symlink
fails closed rather than rebinding the UUID to the link target.

A canonical root must also be disjoint from both managed state namespaces,
`data/vaults` and `cache/vaults`: it may neither contain them nor live within
them. Data and cache may share a configured application root. Ordinary sibling
Vault directories remain supported. Missing canonical directories still permit
status/diagnostic resolution; operations needing existing content keep their
existing availability checks.

Canonical enumeration refuses symlinks, hard-linked files and special nodes
anywhere in the scanned tree. Regular non-Markdown files remain unmanaged and
are not deleted. Destination paths must be relative, contain no `..`, and have
safe existing ancestors and targets. Scoped artifact trees and artifact access
similarly reject linked/special entries. Checks do not create paths; actual
mutations create only their validated parents. These are application ownership
checks with bounded best-effort race protection, not kernel-level isolation.

Existing registries or layouts that violate these checks are left unchanged and
reported unavailable. No automatic path/UUID rewrite, relocation, destructive
cleanup or migration is included. Recovering such an installation requires an
explicit owner decision about its registry or layout. Accepting overlapping
Vaults would require a new ownership/identity contract and is not implemented.
Existing #192 bootstrap migration remains resumable; this issue adds ownership
validation before its existing side effects and introduces no migration phase.

## Exact implementation changes

All paths below are relative to `src/lele_manager/` unless prefixed with `tests/`.

| Files | Change |
| --- | --- |
| `core/vault_filesystem.py` | Shared path, complete-tree and canonical destination checks. |
| `core/vault_registry.py` | Strict authority parsing, equivalent-UUID duplicate detection, canonical/state separation, scoped context validation and validation before create/activation/migration side effects. |
| `core/vault.py`, `cli/import_from_dir.py` | Safe canonical enumeration and destination validation before frontmatter/authoring writes. |
| `application/lesson_writing.py`, `application/lesson_deletion.py` | Controlled domain failures for unsafe canonical namespaces. |
| `adapters/canonical_markdown_vault.py` | Approval publication and verification use the same canonical filesystem boundary. |
| `adapters/json_candidate_repository.py`, `adapters/jsonl_projection_store.py`, `ml/topic_model.py` | Recheck path ownership before staging/projection/model access. |
| `cli/tritalele.py`, `api/server.py` | Capture one CLI approval context; route ordinary API artifact resolution through the existing controlled context failure mapping. |
| `core/vault_snapshot.py` | Reject hard-linked canonical/scoped files and unsafe root ancestors. Preserve canonical-success/derived-failure outcomes. |
| `tests/test_vault_isolation.py` | Synthetic negative, switching, canonical, derived, approval-composition, Ask handler and snapshot/restore regressions. |
| `tests/test_candidate_repository_contract.py` | Expect invalid-parent rejection during the new read preflight; retain controlled-error and redaction assertions. |

## Executable verification

The new regression suite was also run against a temporary export of the original
HEAD implementation: **26 FAIL, 10 PASS**. The new filesystem helper was supplied
only to allow test imports; original modules did not call it. No branch or
worktree was changed for this comparison.

The focused selection includes isolation, candidate approval/repository, CLI
approval, import planning, revision history, Context Pack/assistant resolution,
Danger Zone, API context coherence, projection contracts, paths and runtime
transparency. In particular the restore regression proves that restoring A into
inactive B leaves A, C and active selection untouched, and reports canonical
success independently of an injected derived-refresh failure.

Observed validation in this restricted Python 3.12 environment:

| Check | Observed outcome |
| --- | --- |
| Focused selection above, plus documentation contracts | PASS: 249 tests, including 36 isolation regressions. |
| Original implementation against the isolation regressions | Expected FAIL: 26 failures, 10 passes; demonstrates the gaps rather than assuming registry support proves isolation. |
| `ruff check .` | PASS with available Ruff 0.15.15. The pinned 0.15.22 executable was unavailable; an unrelated installed 0.16.10 has different default rules and was not used as the repository lint gate. |
| Broad `pytest -q --continue-on-collection-errors` checkpoint | FAIL: 1,067 passes, 11 launcher failures from forbidden socket creation (`PermissionError`), 31 module collection errors from missing `fastapi.testclient`. No Vault assertion failed in this run. |
| `mypy src/lele_manager` | FAIL: 25 `import-untyped` errors due to unavailable pandas/scipy stubs and missing typing markers in recovered dependencies. |
| Supplementary mypy with only `import-untyped` disabled | PASS: 96 source files. This does not replace the full type gate. |
| Diff review, `git diff --check`, final status | PASS: changes confined to the listed implementation/tests and this audit; no branch/worktree changes, commits, pushes or publication. |
| Optional AI, live inference, frontend, OS-level security | SKIP: outside this change. |

Dependency recovery used read-only local installations and locally installed
application bundle modules, exposed in `/tmp`; the normal editable development
installation failed because network access is unavailable. No dependency or
network behavior was added to the product. Direct API handler regressions were
used for Ask/activation/snapshot evidence; HTTP TestClient coverage still needs
the complete development environment. A direct ASGI attempt was stopped after
stalling in thread/event-loop dispatch in this restricted environment.

The implementation and focused negative evidence address the demonstrated #264
gaps. Full acceptance is **not certified** while the broad test/type gates are
blocked by this environment. Rerun the repository's normal gates with complete
development dependencies and local socket support before closing the issue.
The separate snapshot editorial-coverage decision above remains architectural
follow-up; no migration or authority redesign is silently supplied here.
