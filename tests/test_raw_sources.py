from pathlib import Path

import pytest

from lele_manager.adapters.raw_sources import (
    InMemorySourceAdapter,
    MarkdownFileSourceAdapter,
    PlainTextFileSourceAdapter,
    SourceDecodingError,
    SourceReadError,
    UnsupportedSourceError,
)
from lele_manager.application.raw_source import RawSource, SourceKind


def test_markdown_file_preserves_content_and_provenance(tmp_path: Path) -> None:
    path = tmp_path / "lesson.md"
    path.write_text("# Héading\n\n body  \n", encoding="utf-8")

    source = MarkdownFileSourceAdapter().load(path)

    assert source.content == "# Héading\n\n body  \n"
    assert source.kind is SourceKind.MARKDOWN
    assert source.logical_name == "lesson.md"
    assert source.filesystem_origin == path


def test_plain_text_file(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("caffè", encoding="utf-8")

    source = PlainTextFileSourceAdapter().load(path, logical_name="notes")

    assert source.content == "caffè"
    assert source.kind is SourceKind.PLAIN_TEXT
    assert source.logical_name == "notes"
    assert source.filesystem_origin == path


def test_stdin_and_in_memory_need_no_filesystem_path() -> None:
    stdin = InMemorySourceAdapter().load("from stdin")
    memory = InMemorySourceAdapter().load(
        "in memory", logical_name="paste", kind=SourceKind.IN_MEMORY
    )

    assert stdin.filesystem_origin is None
    assert stdin.kind is SourceKind.STDIN
    assert memory.filesystem_origin is None
    assert memory.kind is SourceKind.IN_MEMORY


def test_lf_crlf_and_cr_normalize_to_the_same_content_and_fingerprint() -> None:
    sources = [
        RawSource(text, SourceKind.IN_MEMORY, "same")
        for text in ("one\ntwo\n", "one\r\ntwo\r\n", "one\rtwo\r")
    ]

    assert {source.content for source in sources} == {"one\ntwo\n"}
    assert len({source.fingerprint for source in sources}) == 1


def test_empty_input_is_a_valid_source() -> None:
    source = InMemorySourceAdapter().load("")

    assert source.content == ""
    assert source.fingerprint.startswith("sha256:")


def test_fingerprint_is_stable_and_includes_identity() -> None:
    first = RawSource("text", SourceKind.IN_MEMORY, "a")
    same = RawSource("text", SourceKind.IN_MEMORY, "a")
    renamed = RawSource("text", SourceKind.IN_MEMORY, "b")

    assert first.fingerprint == same.fingerprint
    assert first.fingerprint == (
        "sha256:39a8ed5b843155a7a91dd62600ed0fc1d5503de20ddb644f12ee7248aab27072"
    )
    assert first.fingerprint != renamed.fingerprint



def test_filesystem_origin_is_provenance_not_fingerprint_identity() -> None:
    original = RawSource(
        "text",
        SourceKind.MARKDOWN,
        "lesson.md",
        Path("first/location/lesson.md"),
    )
    moved = RawSource(
        "text",
        SourceKind.MARKDOWN,
        "lesson.md",
        Path("second/location/lesson.md"),
    )

    assert original.filesystem_origin != moved.filesystem_origin
    assert original.fingerprint == moved.fingerprint


def test_explicit_empty_logical_name_is_rejected(tmp_path: Path) -> None:
    markdown = tmp_path / "lesson.md"
    markdown.write_text("content", encoding="utf-8")

    text_file = tmp_path / "lesson.txt"
    text_file.write_text("content", encoding="utf-8")

    with pytest.raises(ValueError):
        MarkdownFileSourceAdapter().load(markdown, logical_name="")

    with pytest.raises(ValueError):
        PlainTextFileSourceAdapter().load(text_file, logical_name="")

def test_unreadable_file_has_controlled_error(tmp_path: Path) -> None:
    with pytest.raises(SourceReadError):
        MarkdownFileSourceAdapter().load(tmp_path / "missing.md")


def test_invalid_utf8_has_controlled_error(tmp_path: Path) -> None:
    path = tmp_path / "bad.txt"
    path.write_bytes(b"\xff")

    with pytest.raises(SourceDecodingError):
        PlainTextFileSourceAdapter().load(path)


def test_unsupported_input_has_controlled_error(tmp_path: Path) -> None:
    with pytest.raises(UnsupportedSourceError):
        MarkdownFileSourceAdapter().load(tmp_path / "lesson.txt")
    with pytest.raises(UnsupportedSourceError):
        InMemorySourceAdapter().load(b"bytes")  # type: ignore[arg-type]


def test_adapters_do_not_create_or_stage_candidates(tmp_path: Path) -> None:
    path = tmp_path / "lesson.md"
    path.write_text("content", encoding="utf-8")
    before = sorted(tmp_path.iterdir())

    source = MarkdownFileSourceAdapter().load(path)

    assert source.content == "content"
    assert sorted(tmp_path.iterdir()) == before
    assert not hasattr(source, "candidate_records")
    assert not hasattr(source, "pending_source_writes")
