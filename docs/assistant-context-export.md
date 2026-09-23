# Assistant-ready context export

LeLe Manager provides an explicit assistant-ready context export boundary for
selected maintained knowledge.

This workflow is distinct from the generic Markdown/JSON export.

## Purpose

Assistant-ready context is intended for copying or exporting a bounded set of
LeLe for use with ChatGPT, Codex, or another assistant.

Generation is local. Creating, copying, or exporting assistant context does not
transmit data to an assistant or any other network service.

## Supported scopes

One explicit scope is required per request:

- one or more lesson IDs;
- current search results;
- a Context Pack.

The selected scope controls exactly which LeLe are included.

For explicit lesson IDs and Context Packs, input membership order is preserved.
For search scope, the maintained search result order is preserved.

## Canonical content

Search and other derived state may determine which lesson IDs belong to the
requested scope, but assistant-ready lesson content is read again from the
current canonical Markdown Vault before rendering.

Projection text, search rank, hybrid score, semantic/model state, runtime
diagnostics, canonical revision fingerprints, and filesystem paths are not
included.

## Output

The maintained Markdown representation is deterministic for the same ordered
canonical lesson snapshots.

It contains, where applicable:

- title;
- stable lesson ID;
- lifecycle state;
- topic;
- tags;
- supersession state;
- canonical lesson body;
- typed outgoing relationships.

It intentionally has no generation timestamp.

Example shape:

```text
# LeLe Assistant Context

Scope: 2 LeLe

## First lesson

ID: `python/first`
Lifecycle: `active`
Topic: `python`
Tags: `api`, `testing`

Canonical lesson text.

Relationships:
- extends → `python/base`
- see-also → `testing/contracts`
```

## Broken references

Assistant context must not silently omit requested canonical knowledge.

If a Context Pack contains references that no longer resolve in the current
Vault, assistant-ready export fails explicitly and reports the missing lesson
IDs.

Ambiguous canonical identity or canonical storage/integrity failures also fail
explicitly.

## API

```text
POST /assistant-context
```

Exactly one of these request fields is supplied:

```json
{"lesson_ids":["python/a","python/b"]}
```

```json
{"search":{"q":"deployment","limit":20}}
```

```json
{"context_pack_id":"<context-pack-id>"}
```

Successful responses contain:

```json
{
  "markdown":"...",
  "n_lessons":2,
  "lesson_ids":["python/a","python/b"]
}
```

## Privacy boundary

The endpoint and GUI actions only generate local content.

Clipboard copy and local `.md` download are user-initiated actions. No remote
assistant call, telemetry event, cloud upload, or hidden network transmission
is part of this workflow.
