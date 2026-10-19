# Ask this Vault

`Ask this Vault` is a bounded conversational workflow over maintained knowledge
in the active LeLe Manager Vault. It is not a generic chatbot.

## Grounding

Every question uses exactly one explicit scope:

- explicit LeLe IDs;
- maintained search results;
- one Context Pack.

Search may determine lesson identity and order, but grounding content is read
again from canonical Markdown.

The resulting `ResolvedAssistantContext` is the single authority for both the
knowledge supplied to synthesis and the LeLe IDs that may be cited.

A generated answer cannot cite a LeLe outside that resolved scope.

## Answers and insufficient support

Generated synthesis is presented separately from canonical LeLe content.

An `answered` result requires at least one supporting LeLe citation.

If the selected scope contains insufficient maintained knowledge,
Ask-this-Vault returns the explicit `insufficient-support` outcome rather than
fabricating an answer.

An empty resolved scope returns `insufficient-support` without importing optional
AI dependencies, constructing a backend, or invoking inference.

Lifecycle and supersession metadata are exposed with citations so deprecated,
archived, review-needed, or superseded knowledge is not silently presented as
ordinary current knowledge.

## Provider and privacy boundary

Vault resolution and citation authority are provider-independent.

Provider integration lives behind a replaceable synthesis interface. A
non-empty scope fails closed when no synthesis provider is configured.

The provider is disabled by default. Local Ollama synthesis is available only
through explicit configuration:

| Environment variable | Contract |
| --- | --- |
| `LELE_ASK_VAULT_PROVIDER` | Absent disables synthesis. Only the exact value `ollama` enables it; any other explicitly set value is invalid. |
| `LELE_ASK_VAULT_MODEL` | Required, nonblank model name when enabled; surrounding whitespace is removed. The model must already be available locally. |
| `LELE_ASK_VAULT_TIMEOUT_SECONDS` | Optional finite positive float; defaults to `120.0`. |

The endpoint is fixed at `http://127.0.0.1:11434`. There is no endpoint override,
model download, credential configuration, remote provider, automatic retry, or
fallback. Other provider/model environment variables do not enable synthesis.
When disabled, model and timeout settings are ignored.

For an enabled, nonempty scope, the optional GiadaWare AI dependency must be
available and compatible. Import, configuration, and construction failures
produce a redacted provider-unavailable error. Composition itself performs no
inference. Each question makes at most one inference call.

The local provider receives the normalized question and the resolved canonical
lessons' IDs, title, topic, tags, text, lifecycle, supersession and relationships.
Filesystem paths, canonical revisions, source, importance, dates, and review
metadata are excluded. Schema and deterministic output validation enforce the
existing input, answer, result-size and citation bounds. Structural validation
does not establish factual truth or semantic qualification.

No remote provider is enabled implicitly. Resolving scope, reading canonical
Markdown, and displaying the Ask UI do not themselves transmit Vault content.

Any future remote integration must explicitly disclose transmitted content,
credentials, consent, and network behavior while preserving LeLe Manager's
local-first privacy model.

## Canonical authority

Ask-this-Vault is advisory.

Generated answers never mutate canonical Markdown, lifecycle state,
relationships, Context Packs, or projections. Maintained knowledge can change
only through the existing explicit authoring workflow.

## API

`POST /ask-vault`

The request contains a question and exactly one assistant-context scope.

Before scope resolution or provider composition, the question is stripped of
surrounding whitespace and validated to contain 1–4000 Unicode code points.
Surrogate characters are rejected. Canonical scope resolution then follows the
same contract as `/assistant-context`.

Ask-this-Vault failures use fixed, redacted details:

| HTTP status | Error code |
| --- | --- |
| 422 | `ask_vault_question_invalid` |
| 502 | `ask_vault_invalid_result` |
| 503 | `ask_vault_provider_unavailable` |
| 504 | `ask_vault_provider_timeout` |

Scope-resolution errors retain their existing codes. No dependency diagnostics,
provider exception text, or credentials are included in the Ask-this-Vault errors.

Responses expose:

- `outcome`;
- generated `answer`;
- `generated_synthesis`;
- canonical supporting `citations`;
- `scope_lesson_ids`.

Every citation ID is validated against the resolved `scope_lesson_ids`.

The GUI exposes the workflow for current Browse results, selected Browse LeLe,
a Detail LeLe, and Context Packs.

## Python distribution and test boundaries

LeLe core remains Python `>=3.10` and does not depend on GiadaWare AI. The
optional AI integration requires Python `>=3.11` and explicit provider opt-in.
The qualified experimental distribution is the canonical wheel from
[GiadaWare AI v0.0.2](https://github.com/gcomneno/giadaware-ai/releases/tag/v0.0.2).
Historical `local-superseded-*` release assets are excluded.

Core tests collect without optional AI imports:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
```

Optional tests require a separately installed, verified wheel:

```bash
python scripts/acquire-optional-ai.py download /tmp/lele-optional-ai
python -m pip install --no-index --no-deps /tmp/lele-optional-ai/giadaware_ai-0.0.2-py3-none-any.whl
python scripts/acquire-optional-ai.py verify-installed
python -m pytest -q --optional-ai tests/optional_ai
```

Use a fresh download directory and an isolated environment. Acquisition checks
the pinned SHA-256 before opening wheel metadata or publishing the file, then
checks distribution identity, version and Python requirement. Installation uses
only that file. Installed provenance and import location are checked separately;
another local `0.0.2` wheel or an upstream source path is insufficient. Download,
integrity and identity errors stop the job, with no PyPI fallback.

`tests/optional_ai/` is excluded before import by default, and enabled explicitly
with `--optional-ai`. Missing dependencies then fail collection/execution rather
than skipping tests. Provider-independent scope, validation, disabled-provider
and error contracts remain in core; real optional API contracts use fake
backends in the optional group. Zero optional imports replace constructor-spy
checks in core, proving that construction cannot occur with the dependency absent.
The optional group's fixture forbids socket connections and DNS access.

CI selects core Python 3.10/3.12 and optional-AI Python 3.11/3.12. Python 3.10
development and packaging tests use conditional `tomli`; core runtime gains no
TOML dependency. Native release tooling continues to select Python 3.12.

These gates qualify distribution and deterministic consumer behavior. Real
Ollama inference and semantic quality remain outside their scope. See the
[qualification evidence](issue-262-m4.2-qualification.md) for observed results
and outstanding CI verification.
