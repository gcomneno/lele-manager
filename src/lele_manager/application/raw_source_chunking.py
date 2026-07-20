"""Deterministic, backend-neutral chunking of normalized raw sources.

Chunks are exact slices of ``RawSource.content``. Paragraphs and Markdown ATX
headings are preferred boundaries. A block larger than ``max_characters`` is
split at the last line ending that fits, or at exactly ``max_characters`` when
no line ending is available. All sizes and offsets count Python Unicode
characters, not encoded bytes or tokenizer-specific units.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol, Sequence

from lele_manager.application.raw_source import RawSource, SourceKind, SourceSpan


_HEADING = re.compile(
    r"^[ ]{0,3}(#{1,6})[ \t]+(.+?)(?:[ \t]+#+[ \t]*)?$"
)
_FENCE_OPEN = re.compile(r"^[ ]{0,3}(`{3,}|~{3,})(.*)$")


@dataclass(frozen=True)
class ChunkingSettings:
    """Explicit limits controlling deterministic source chunking."""

    max_characters: int = 2_000

    def __post_init__(self) -> None:
        if (
            isinstance(self.max_characters, bool)
            or not isinstance(self.max_characters, int)
            or self.max_characters < 1
        ):
            raise ValueError("max characters must be a positive integer")


@dataclass(frozen=True)
class RawSourceChunk:
    """One immutable source slice and its stable downstream identity inputs."""

    text: str
    source_fingerprint: str
    source_kind: SourceKind
    source_logical_name: str
    index: int
    source_span: SourceSpan
    heading_context: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise TypeError("chunk text must be a string")
        if not self.text.strip():
            raise ValueError("chunk text must contain non-whitespace content")
        if not isinstance(self.source_fingerprint, str) or not self.source_fingerprint:
            raise ValueError("source fingerprint must not be empty")
        if not isinstance(self.source_kind, SourceKind):
            raise TypeError("source kind must be a SourceKind")
        if (
            not isinstance(self.source_logical_name, str)
            or not self.source_logical_name
        ):
            raise ValueError("source logical name must not be empty")
        if (
            isinstance(self.index, bool)
            or not isinstance(self.index, int)
            or self.index < 0
        ):
            raise ValueError("chunk index must be a non-negative integer")
        if not isinstance(self.source_span, SourceSpan):
            raise TypeError("source span must be a SourceSpan")
        if self.source_span.end - self.source_span.start != len(self.text):
            raise ValueError("source span length must match chunk text length")
        if not isinstance(self.heading_context, tuple) or not all(
            isinstance(heading, str) and heading for heading in self.heading_context
        ):
            raise ValueError("heading context must be a tuple of non-empty strings")


class RawSourceChunker(Protocol):
    """Port implemented by deterministic raw-source chunkers."""

    def chunk(
        self, source: RawSource, settings: ChunkingSettings = ChunkingSettings()
    ) -> Sequence[RawSourceChunk]: ...


@dataclass(frozen=True)
class _Piece:
    start: int
    end: int
    heading_context: tuple[str, ...]


class DeterministicRawSourceChunker:
    """Character-bounded chunker using source-native semantic boundaries."""

    def chunk(
        self, source: RawSource, settings: ChunkingSettings = ChunkingSettings()
    ) -> tuple[RawSourceChunk, ...]:
        if not isinstance(source, RawSource):
            raise TypeError("source must be a RawSource")
        if not isinstance(settings, ChunkingSettings):
            raise TypeError("settings must be ChunkingSettings")
        if not source.content or not source.content.strip():
            return ()

        pieces = self._pieces(source, settings.max_characters)
        chunks: list[RawSourceChunk] = []
        for piece in pieces:
            text = source.content[piece.start : piece.end]
            if not text.strip():
                continue
            chunks.append(
                RawSourceChunk(
                    text=text,
                    source_fingerprint=source.fingerprint,
                    source_kind=source.kind,
                    source_logical_name=source.logical_name,
                    index=len(chunks),
                    source_span=SourceSpan(piece.start, piece.end),
                    heading_context=piece.heading_context,
                )
            )
        return tuple(chunks)

    def _pieces(self, source: RawSource, limit: int) -> list[_Piece]:
        blocks = self._semantic_blocks(source)
        pieces: list[_Piece] = []
        pending: _Piece | None = None
        for block in blocks:
            for part in self._split_oversized(source.content, block, limit):
                if (
                    pending is not None
                    and pending.heading_context == part.heading_context
                    and pending.end - pending.start + part.end - part.start <= limit
                ):
                    pending = _Piece(pending.start, part.end, pending.heading_context)
                else:
                    if pending is not None:
                        pieces.append(pending)
                    pending = part
        if pending is not None:
            pieces.append(pending)
        return pieces

    def _semantic_blocks(self, source: RawSource) -> list[_Piece]:
        content = source.content
        boundaries = {0, len(content)}
        offset = 0
        fence: tuple[str, int] | None = None
        for line in content.splitlines(keepends=True):
            line_end = offset + len(line)
            line_without_newline = line.rstrip("\n")

            if source.kind is SourceKind.MARKDOWN:
                if fence is not None:
                    marker, minimum_length = fence
                    closing = re.fullmatch(
                        rf"[ ]{{0,3}}{re.escape(marker)}"
                        rf"{{{minimum_length},}}[ \t]*",
                        line_without_newline,
                    )
                    if closing:
                        boundaries.add(line_end)
                        fence = None
                    offset = line_end
                    continue

                opening = _FENCE_OPEN.match(line_without_newline)
                if opening:
                    marker = opening.group(1)
                    boundaries.add(offset)
                    fence = (marker[0], len(marker))
                    offset = line_end
                    continue

                if _HEADING.match(line_without_newline):
                    boundaries.add(offset)
                    boundaries.add(line_end)

            if not line.strip():
                boundaries.add(line_end)
            offset = line_end

        contexts: list[str] = []
        blocks: list[_Piece] = []
        ordered = sorted(boundaries)
        for start, end in zip(ordered, ordered[1:]):
            if start == end:
                continue
            text = content[start:end]
            if source.kind is SourceKind.MARKDOWN:
                match = _HEADING.match(text.rstrip("\n"))
                if match:
                    level = len(match.group(1))
                    contexts = contexts[: level - 1]
                    contexts.append(match.group(2).strip())
            blocks.append(_Piece(start, end, tuple(contexts)))
        return blocks

    @staticmethod
    def _split_oversized(content: str, piece: _Piece, limit: int) -> list[_Piece]:
        parts: list[_Piece] = []
        start = piece.start
        while piece.end - start > limit:
            hard_end = start + limit
            newline = content.rfind("\n", start, hard_end)
            end = newline + 1 if newline >= start else hard_end
            parts.append(_Piece(start, end, piece.heading_context))
            start = end
        if start < piece.end:
            parts.append(_Piece(start, piece.end, piece.heading_context))
        return parts
