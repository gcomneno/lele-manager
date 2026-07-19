"""Backend-neutral raw source contract.

Line endings are the only content normalization performed: CRLF and lone CR are
converted to LF. Whitespace, Unicode characters, a possible BOM, and the
presence or absence of a final newline are preserved.

The fingerprint identifies normalized source content, source kind and logical
name. The optional filesystem origin is retained as provenance but deliberately
excluded from identity, so moving the same logical source does not change its
fingerprint.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
from pathlib import Path


class SourceKind(str, Enum):
    """Supported raw-source identities."""

    MARKDOWN = "markdown"
    PLAIN_TEXT = "plain_text"
    STDIN = "stdin"
    IN_MEMORY = "in_memory"


def normalize_line_endings(content: str) -> str:
    """Convert CRLF and lone CR line endings to LF, changing nothing else."""
    return content.replace("\r\n", "\n").replace("\r", "\n")


@dataclass(frozen=True)
class RawSource:
    """Normalized source content together with all source-level provenance."""

    content: str
    kind: SourceKind
    logical_name: str
    filesystem_origin: Path | None = None
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.content, str):
            raise TypeError("raw source content must be a string")
        if not isinstance(self.kind, SourceKind):
            raise TypeError("raw source kind must be a SourceKind")
        if not isinstance(self.logical_name, str) or not self.logical_name:
            raise ValueError("raw source logical name must not be empty")
        if self.filesystem_origin is not None and not isinstance(
            self.filesystem_origin, Path
        ):
            raise TypeError("filesystem origin must be a pathlib.Path or None")

        normalized = normalize_line_endings(self.content)
        object.__setattr__(self, "content", normalized)
        identity = {
            "content": normalized,
            "kind": self.kind.value,
            "logical_name": self.logical_name,
        }
        payload = json.dumps(
            identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        object.__setattr__(
            self, "fingerprint", f"sha256:{hashlib.sha256(payload).hexdigest()}"
        )
