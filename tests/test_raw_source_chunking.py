from dataclasses import FrozenInstanceError

import pytest

from lele_manager.application.raw_source import RawSource, SourceKind, SourceSpan
from lele_manager.application.raw_source_chunking import (
    ChunkingSettings,
    DeterministicRawSourceChunker,
    RawSourceChunk,
    RawSourceChunker,
)


def chunks(content: str, kind: SourceKind, maximum: int) -> tuple[RawSourceChunk, ...]:
    source = RawSource(content, kind, "source")
    return DeterministicRawSourceChunker().chunk(
        source, ChunkingSettings(max_characters=maximum)
    )


def test_contract_and_outputs_are_typed_and_immutable() -> None:
    chunker: RawSourceChunker = DeterministicRawSourceChunker()
    settings = ChunkingSettings(max_characters=20)
    result = chunker.chunk(RawSource("text", SourceKind.PLAIN_TEXT, "notes"), settings)

    assert result[0].source_span == SourceSpan(0, 4)
    assert result[0].source_kind is SourceKind.PLAIN_TEXT
    assert result[0].source_logical_name == "notes"
    with pytest.raises(FrozenInstanceError):
        settings.max_characters = 10  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result[0].text = "changed"  # type: ignore[misc]


@pytest.mark.parametrize("invalid_text", ["", " \n\t"])
def test_chunk_output_rejects_empty_or_whitespace_only_text(
    invalid_text: str,
) -> None:
    with pytest.raises(ValueError, match="non-whitespace"):
        RawSourceChunk(
            text=invalid_text,
            source_fingerprint="sha256:source",
            source_kind=SourceKind.PLAIN_TEXT,
            source_logical_name="notes",
            index=0,
            source_span=SourceSpan(0, len(invalid_text)),
        )


def test_chunk_output_rejects_non_string_text() -> None:
    with pytest.raises(TypeError, match="chunk text must be a string"):
        RawSourceChunk(
            text=object(),  # type: ignore[arg-type]
            source_fingerprint="sha256:source",
            source_kind=SourceKind.PLAIN_TEXT,
            source_logical_name="notes",
            index=0,
            source_span=SourceSpan(0, 1),
        )


def test_chunk_output_rejects_a_span_that_does_not_match_text_length() -> None:
    with pytest.raises(ValueError, match="span length"):
        RawSourceChunk(
            text="abcd",
            source_fingerprint="sha256:source",
            source_kind=SourceKind.PLAIN_TEXT,
            source_logical_name="notes",
            index=0,
            source_span=SourceSpan(10, 15),
        )



@pytest.mark.parametrize("value", [0, -1, True, 1.5, "10"])
def test_invalid_settings_are_rejected(value: object) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        ChunkingSettings(max_characters=value)  # type: ignore[arg-type]


@pytest.mark.parametrize("content", ["", " \n\t"])
def test_empty_or_whitespace_only_input_produces_no_chunks(content: str) -> None:
    assert chunks(content, SourceKind.PLAIN_TEXT, 10) == ()


def test_exact_boundary_and_one_character_over_use_character_offsets() -> None:
    assert [item.text for item in chunks("café😀", SourceKind.PLAIN_TEXT, 5)] == [
        "café😀"
    ]
    over = chunks("café😀x", SourceKind.PLAIN_TEXT, 5)
    assert [item.text for item in over] == ["café😀", "x"]
    assert [item.source_span for item in over] == [SourceSpan(0, 5), SourceSpan(5, 6)]


def test_plain_text_prefers_paragraphs_and_never_emits_empty_chunks() -> None:
    result = chunks("alpha\n\nbeta\n\ngamma", SourceKind.PLAIN_TEXT, 13)

    assert [item.text for item in result] == ["alpha\n\nbeta\n\n", "gamma"]
    assert all(item.text and item.text.strip() for item in result)


def test_markdown_heading_context_is_predictable_and_not_prepended() -> None:
    content = "# Café 😀\n\nintro\n\n## Details\n\nbody\n\n# Next\n\nend"
    result = chunks(content, SourceKind.MARKDOWN, 18)

    assert [(item.text, item.heading_context) for item in result] == [
        ("# Café 😀\n\nintro\n\n", ("Café 😀",)),
        ("## Details\n\nbody\n\n", ("Café 😀", "Details")),
        ("# Next\n\nend", ("Next",)),
    ]


@pytest.mark.parametrize(
    ("opening", "closing"),
    [
        ("```python", "```"),
        ("~~~python", "~~~"),
    ],
)
def test_markdown_headings_inside_fenced_code_do_not_change_context(
    opening: str,
    closing: str,
) -> None:
    content = (
        "# Titolo reale\n\n"
        f"{opening}\n"
        "# Questo è codice, non un titolo\n"
        "print('ciao')\n"
        f"{closing}\n\n"
        "Testo conclusivo"
    )

    result = chunks(content, SourceKind.MARKDOWN, 40)

    assert len(result) > 1
    assert all(item.heading_context == ("Titolo reale",) for item in result)
    assert all(
        "Questo è codice, non un titolo" not in item.heading_context
        for item in result
    )


def test_markdown_atx_heading_accepts_up_to_three_leading_spaces() -> None:
    result = chunks(
        "   # Titolo indentato\n\nContenuto",
        SourceKind.MARKDOWN,
        100,
    )

    assert len(result) == 1
    assert result[0].heading_context == ("Titolo indentato",)



def test_oversized_blocks_fall_back_to_line_then_hard_character_boundaries() -> None:
    plain = chunks("abcd\nefghijkl", SourceKind.PLAIN_TEXT, 6)
    unbroken = chunks("abcdefghijklm", SourceKind.PLAIN_TEXT, 6)

    assert [item.text for item in plain] == ["abcd\n", "efghij", "kl"]
    assert [item.text for item in unbroken] == ["abcdef", "ghijkl", "m"]


def test_newline_exactly_at_limit_never_creates_an_oversized_chunk() -> None:
    result = chunks("abcdef\nresto", SourceKind.PLAIN_TEXT, 6)

    assert [item.text for item in result] == ["abcdef", "\nresto"]
    assert [item.source_span for item in result] == [
        SourceSpan(0, 6),
        SourceSpan(6, 12),
    ]
    assert all(len(item.text) <= 6 for item in result)



def test_oversized_markdown_block_keeps_heading_context_during_fallback() -> None:
    result = chunks("# Topic\nabcdefghijk", SourceKind.MARKDOWN, 6)

    assert [item.text for item in result] == ["# Topi", "c\n", "abcdef", "ghijk"]
    assert all(item.heading_context == ("Topic",) for item in result)


def test_lf_normalization_spans_and_repeated_runs_are_value_equivalent() -> None:
    source = RawSource("one\r\n\r\ntwö 😀\rthree", SourceKind.PLAIN_TEXT, "notes")
    settings = ChunkingSettings(max_characters=7)
    chunker = DeterministicRawSourceChunker()

    first = chunker.chunk(source, settings)
    second = chunker.chunk(source, settings)

    assert first == second
    assert repr(first).encode("utf-8") == repr(second).encode("utf-8")
    assert [item.index for item in first] == list(range(len(first)))
    assert all(item.source_fingerprint == source.fingerprint for item in first)
    assert all(
        item.text == source.content[item.source_span.start : item.source_span.end]
        for item in first
    )


def test_single_markdown_block_is_preserved_when_it_fits() -> None:
    result = chunks("# Heading\nbody", SourceKind.MARKDOWN, 50)

    assert len(result) == 1
    assert result[0].text == "# Heading\nbody"
    assert result[0].heading_context == ("Heading",)
