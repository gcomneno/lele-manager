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

An empty resolved scope does not invoke a synthesis provider.

Lifecycle and supersession metadata are exposed with citations so deprecated,
archived, review-needed, or superseded knowledge is not silently presented as
ordinary current knowledge.

## Provider and privacy boundary

Vault resolution and citation authority are provider-independent.

Provider integration lives behind a replaceable synthesis interface. A
non-empty scope fails closed when no synthesis provider is configured.

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

Responses expose:

- `outcome`;
- generated `answer`;
- `generated_synthesis`;
- canonical supporting `citations`;
- `scope_lesson_ids`.

Every citation ID is validated against the resolved `scope_lesson_ids`.

The GUI exposes the workflow for current Browse results, selected Browse LeLe,
a Detail LeLe, and Context Packs.
