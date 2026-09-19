from __future__ import annotations

import json

import pytest

pytest.importorskip(
    "giadaware_ai",
    reason="GiadaWare AI is an optional semantic runtime dependency",
)

from giadaware_ai import (  # noqa: E402
    AIInvalidResponseError,
    AIUnavailableError,
    CapabilityFamily,
)

from lele_manager.adapters.giadaware_ai_semantic_extraction import (
    ExtractLessonCandidatesCapability,
)
from lele_manager.application.raw_source import RawSource, SourceKind
from lele_manager.application.raw_source_chunking import (
    ChunkingSettings,
    DeterministicRawSourceChunker,
)
from lele_manager.application.semantic_lesson_extraction import (
    SemanticExtractionError,
    SemanticExtractionInput,
)


class RecordingBackend:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_schema: object = None,
    ) -> object:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "response_schema": response_schema,
            }
        )
        return self.response


class UnavailableBackend:
    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_schema: object = None,
    ) -> object:
        raise AIUnavailableError("private backend detail")


def semantic_input() -> SemanticExtractionInput:
    source = RawSource(
        "# Reliability\n\nValidate external data.\n\n"
        "Keep mutation authority in application code.\n",
        SourceKind.MARKDOWN,
        "/private/path/notes.md",
    )
    chunks = DeterministicRawSourceChunker().chunk(
        source,
        ChunkingSettings(max_characters=32),
    )
    return SemanticExtractionInput(chunks)


def raw_proposal(
    *,
    supporting: list[int] | None = None,
) -> dict[str, object]:
    return {
        "title": "Validate external data",
        "body": "Validate untrusted external data before it crosses authority boundaries.",
        "rationale": "The supplied source explicitly says to validate external data.",
        "supporting_chunk_indexes": [1] if supporting is None else supporting,
        "topic": "architecture",
        "tags": ["validation", "boundaries"],
        "source_label": "engineering-notes",
        "importance": 4,
    }


def test_capability_is_consumer_owned_extract_specialization() -> None:
    capability = ExtractLessonCandidatesCapability(RecordingBackend({"proposals": []}))

    assert capability.family is CapabilityFamily.EXTRACT


def test_empty_input_returns_zero_without_backend_call() -> None:
    backend = RecordingBackend({"proposals": [raw_proposal()]})
    capability = ExtractLessonCandidatesCapability(backend)

    result = capability.execute(SemanticExtractionInput(()))

    assert result.proposals == ()
    assert backend.calls == []


def test_zero_one_and_many_proposals_are_supported() -> None:
    value = semantic_input()
    indexes = [chunk.index for chunk in value.chunks]

    for response, expected in (
        ({"proposals": []}, 0),
        ({"proposals": [raw_proposal(supporting=[indexes[0]])]}, 1),
        (
            {
                "proposals": [
                    raw_proposal(supporting=[indexes[0]]),
                    {
                        **raw_proposal(supporting=[indexes[-1]]),
                        "title": "Keep authority deterministic",
                        "body": "Keep mutation authority in deterministic application code.",
                    },
                ]
            },
            2,
        ),
    ):
        result = ExtractLessonCandidatesCapability(RecordingBackend(response)).execute(
            value
        )

        assert len(result.proposals) == expected


def test_backend_receives_only_bounded_chunk_content_and_heading_context() -> None:
    value = semantic_input()
    backend = RecordingBackend({"proposals": []})

    ExtractLessonCandidatesCapability(backend).execute(value)

    assert len(backend.calls) == 1
    call = backend.calls[0]
    payload = json.loads(call["user_prompt"])

    assert set(payload) == {"chunks"}
    assert len(payload["chunks"]) == len(value.chunks)
    assert all(
        set(chunk) == {"heading_context", "index", "text"}
        for chunk in payload["chunks"]
    )

    serialized = call["user_prompt"]
    assert "/private/path/notes.md" not in serialized
    assert value.chunks[0].source_fingerprint not in serialized
    assert "source_fingerprint" not in serialized
    assert "source_logical_name" not in serialized

    schema = call["response_schema"]
    assert isinstance(schema, dict)
    assert "ollama" not in repr(schema).lower()
    assert "openai" not in repr(schema).lower()
    assert "deepseek" not in repr(schema).lower()
    assert "format" not in schema


def test_result_is_typed_and_metadata_remains_advisory() -> None:
    value = semantic_input()
    index = value.chunks[0].index
    backend = RecordingBackend({"proposals": [raw_proposal(supporting=[index])]})

    result = ExtractLessonCandidatesCapability(backend).execute(value)
    proposal = result.proposals[0]

    assert proposal.title == "Validate external data"
    assert proposal.supporting_chunk_indexes == (index,)
    assert proposal.topic == "architecture"
    assert proposal.tags == ("validation", "boundaries")
    assert proposal.source_label == "engineering-notes"
    assert proposal.importance == 4


@pytest.mark.parametrize(
    "response",
    [
        {},
        {"proposals": [], "approved": True},
        {"proposals": "not-an-array"},
        {"proposals": [{"title": "incomplete"}]},
        {
            "proposals": [
                {
                    **raw_proposal(),
                    "approved": True,
                }
            ]
        },
        {
            "proposals": [
                {
                    **raw_proposal(),
                    "supporting_chunk_indexes": [],
                }
            ]
        },
        {
            "proposals": [
                {
                    **raw_proposal(),
                    "importance": True,
                }
            ]
        },
    ],
)
def test_invalid_model_output_fails_closed(
    response: object,
) -> None:
    with pytest.raises(AIInvalidResponseError):
        ExtractLessonCandidatesCapability(RecordingBackend(response)).execute(
            semantic_input()
        )


def test_unknown_supporting_chunk_fails_closed() -> None:
    with pytest.raises(
        AIInvalidResponseError,
        match="unknown source chunk",
    ):
        ExtractLessonCandidatesCapability(
            RecordingBackend({"proposals": [raw_proposal(supporting=[999])]})
        ).execute(semantic_input())


def test_backend_failure_is_exposed_as_controlled_semantic_failure() -> None:
    with pytest.raises(
        SemanticExtractionError,
        match="semantic extraction backend failed",
    ) as caught:
        ExtractLessonCandidatesCapability(UnavailableBackend()).execute(
            semantic_input()
        )

    assert "private backend detail" not in str(caught.value)


def test_prompt_explicitly_excludes_authority_and_fabrication() -> None:
    backend = RecordingBackend({"proposals": []})

    ExtractLessonCandidatesCapability(backend).execute(semantic_input())

    prompt = str(backend.calls[0]["system_prompt"]).lower()
    assert "do not invent" in prompt
    assert "zero, one, or many" in prompt
    assert "approval" in prompt
    assert "publication" in prompt
    assert "authority" in prompt
