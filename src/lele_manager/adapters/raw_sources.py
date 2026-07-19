"""UTF-8 file and in-memory adapters for the raw-source contract."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lele_manager.application.raw_source import RawSource, SourceKind


class RawSourceError(Exception):
    """Base class for controlled raw-source adapter failures."""


class SourceReadError(RawSourceError):
    """A filesystem source could not be read."""


class SourceDecodingError(RawSourceError):
    """Source bytes were not valid UTF-8."""


class UnsupportedSourceError(RawSourceError):
    """An adapter was given an input it does not support."""


def _read_utf8(path: Path) -> str:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise SourceReadError(f"could not read source file {path}: {exc}") from exc
    try:
        return raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise SourceDecodingError(f"source file is not valid UTF-8: {path}") from exc


@dataclass(frozen=True)
class MarkdownFileSourceAdapter:
    """Read one UTF-8 Markdown file without interpreting its Markdown."""

    def load(self, path: Path | str, *, logical_name: str | None = None) -> RawSource:
        origin = Path(path)
        if origin.suffix.lower() not in {".md", ".markdown"}:
            raise UnsupportedSourceError(f"not a Markdown source file: {origin}")
        return RawSource(
            content=_read_utf8(origin),
            kind=SourceKind.MARKDOWN,
            logical_name=origin.name if logical_name is None else logical_name,
            filesystem_origin=origin,
        )


@dataclass(frozen=True)
class PlainTextFileSourceAdapter:
    """Read one UTF-8 plain-text file."""

    def load(self, path: Path | str, *, logical_name: str | None = None) -> RawSource:
        origin = Path(path)
        if origin.suffix.lower() != ".txt":
            raise UnsupportedSourceError(f"not a plain-text source file: {origin}")
        return RawSource(
            content=_read_utf8(origin),
            kind=SourceKind.PLAIN_TEXT,
            logical_name=origin.name if logical_name is None else logical_name,
            filesystem_origin=origin,
        )


@dataclass(frozen=True)
class InMemorySourceAdapter:
    """Adapt supplied content; reading/parsing a terminal is deliberately external."""

    def load(
        self,
        content: str,
        *,
        logical_name: str = "stdin",
        kind: SourceKind = SourceKind.STDIN,
    ) -> RawSource:
        if not isinstance(content, str):
            raise UnsupportedSourceError("in-memory source content must be a string")
        if kind not in {SourceKind.STDIN, SourceKind.IN_MEMORY}:
            raise UnsupportedSourceError(
                "in-memory adapter supports only stdin and in_memory source kinds"
            )
        return RawSource(content=content, kind=kind, logical_name=logical_name)


# This name makes the stdin use case explicit without coupling it to sys.stdin.
StdinSourceAdapter = InMemorySourceAdapter
