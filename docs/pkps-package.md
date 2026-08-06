# LeLe Manager local PKPS consumer contract v1

[English](pkps-package.md) | [Italiano](it/pkps-package.md)

This document describes only the **local PKPS consumer implemented by
LeLe Manager**. It does not describe the complete PKPS project, its
cross-repository orchestration, or the future canonical protocol contract.

The boundary supports hand-off between GYTE Study Tools and LeLe Manager. GYTE
owns its private workspace and source materials; LeLe Manager owns candidate
review, explicit approval, canonical Markdown, and derived data.

## Package

LeLe accepts a package directory whose root contains `pkps-manifest.json` and
the declared lesson, or a ZIP with exactly one root directory containing those
same files. The v1 manifest requires:

```json
{
  "schema_version": 1,
  "package_id": "stable-producer-identifier",
  "producer": {"name": "gyte-study-tools", "version": "0.1.0"},
  "created_at": "2026-08-06T09:00:00Z",
  "lesson": {"path": "lesson.md", "sha256": "…", "bytes": 123},
  "source": {"type": "youtube", "url": "https://example.invalid/watch"}
}
```

`schema_version` is exactly `1`; `package_id` and `producer.version` are
non-empty strings; `created_at` is a UTC timestamp; `source.type` is `youtube`
or `article`; and `source.url` is an absolute HTTP/HTTPS URL. `source.title`
and other source identifiers are optional and retained as provenance. The
lesson SHA-256 is lowercase hexadecimal and its byte count is positive.

The lesson path is a normalized relative POSIX path. Absolute paths, `..`,
symlinks, missing files, non-files, and escapes from the package root are
rejected. ZIP input also rejects traversal, absolute or non-normalized paths,
duplicate entries, symlinks, and ambiguous/multiple roots.

## Import and lifecycle

```bash
lele pkps import PACKAGE_PATH
lele pkps import PACKAGE_PATH --json
```

Import validates the package before it stages exactly one ordinary TritaLeLe
candidate. It does not write the canonical vault, JSONL projection, or ML
artifacts, and it does not refresh projections. The usual TritaLeLe review,
accept, and explicit approval flow remains the only route to canonical
Markdown.

Package identity is `package_id`; content identity is `lesson.sha256`. A
repeat import with both values unchanged reuses the existing candidate. Reusing
the same package ID with another content hash is a controlled conflict.
Different package IDs with the same content remain separate review candidates;
LeLe's existing duplicate workflow decides what to do with them.

Candidate provenance stores the original normalized manifest, package and
producer identity, package timestamp, source data, content digest and length,
and the local import timestamp. That immutable provenance is shown by the
existing candidate workflow and is copied into the canonical approval trace.

Publication references such as PDF, EPUB, and Kindle metadata may be retained
in the manifest, but v1 neither imports those artifacts nor transfers authority
over them to LeLe.

## Resource and path limits

PKPS v1 treats package input as untrusted local data. The package path itself,
the manifest, the declared lesson, and every relevant intermediate directory
must not be symbolic links.

The importer enforces these limits before reading complete content:

- manifest: 256 KiB;
- Markdown lesson: 16 MiB;
- ZIP entries: 128;
- total uncompressed ZIP content: 32 MiB.

ZIP content is inspected in place and is never extracted. Packages exceeding
these limits fail with controlled PKPS domain errors.
