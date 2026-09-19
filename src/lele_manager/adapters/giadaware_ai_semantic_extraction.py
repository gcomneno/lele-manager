"""GiadaWare AI adapter for advisory TritaLeLe Lesson Learned extraction.

The concrete capability is consumer-owned by LeLe Manager.  GiadaWare AI
provides the semantic Extract family and provider-independent AIBackend
boundary; LeLe Manager owns the lesson schema, deterministic validation,
source provenance, staging, review, approval, and publication authority.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Final

from giadaware_ai import (
    AIError,
    AIInvalidResponseError,
    ExtractCapability,
)

from lele_manager.application.semantic_lesson_extraction import (
    SemanticExtractionError,
    SemanticExtractionInput,
    SemanticLessonExtractionResult,
    SemanticLessonProposal,
)


_SYSTEM_PROMPT: Final = """\
Extract reusable Lesson Learned proposals only from the supplied source chunks.

Rules:
- Return zero, one, or many proposals. Never force one proposal per chunk.
- A proposal must express a reusable lesson, not boilerplate, narration, or a
  source-specific incidental detail.
- Distill and rewrite for clarity, but do not invent claims unsupported by the
  supplied chunks.
- Every proposal must cite one or more supplied chunk indexes that directly
  support it.
- Use only the supplied chunk text and heading context as evidence.
- Do not claim approval, verification, publication readiness, correctness, or
  execution authority.
- Suggested metadata and rationale are advisory only.
- Do not invent dates.
- Do not merge, discard, persist, publish, or modify any consumer data.
"""


_RESPONSE_SCHEMA: Final[dict[str, object]] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["proposals"],
    "properties": {
        "proposals": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "title",
                    "body",
                    "rationale",
                    "supporting_chunk_indexes",
                    "topic",
                    "tags",
                    "source_label",
                    "importance",
                ],
                "properties": {
                    "title": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "body": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "rationale": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "supporting_chunk_indexes": {
                        "type": "array",
                        "minItems": 1,
                        "uniqueItems": True,
                        "items": {
                            "type": "integer",
                            "minimum": 0,
                        },
                    },
                    "topic": {
                        "anyOf": [
                            {"type": "string", "minLength": 1},
                            {"type": "null"},
                        ]
                    },
                    "tags": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "minLength": 1,
                        },
                    },
                    "source_label": {
                        "anyOf": [
                            {"type": "string", "minLength": 1},
                            {"type": "null"},
                        ]
                    },
                    "importance": {
                        "anyOf": [
                            {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 5,
                            },
                            {"type": "null"},
                        ]
                    },
                },
            },
        }
    },
}


_PROPOSAL_FIELDS = {
    "title",
    "body",
    "rationale",
    "supporting_chunk_indexes",
    "topic",
    "tags",
    "source_label",
    "importance",
}


def _invalid(message: str) -> AIInvalidResponseError:
    return AIInvalidResponseError(message)


def _optional_string(value: object, name: str) -> str | None:
    if value is None:
        return None
    if type(value) is not str or not value.strip():
        raise _invalid(f"{name} must be null or a non-empty string")
    if any("\ud800" <= character <= "\udfff" for character in value):
        raise _invalid(f"{name} contains invalid Unicode")
    return value


class ExtractLessonCandidatesCapability(
    ExtractCapability[
        SemanticExtractionInput,
        SemanticLessonExtractionResult,
    ]
):
    """Extract advisory Lesson Learned proposals from bounded source chunks."""

    def execute(
        self,
        value: SemanticExtractionInput,
    ) -> SemanticLessonExtractionResult:
        if type(value) is not SemanticExtractionInput:
            raise TypeError("value must be a SemanticExtractionInput")

        if not value.chunks:
            return SemanticLessonExtractionResult(())

        payload = {
            "chunks": [
                {
                    "heading_context": list(chunk.heading_context),
                    "index": chunk.index,
                    "text": chunk.text,
                }
                for chunk in value.chunks
            ]
        }

        try:
            raw = self._backend.generate_json(
                system_prompt=_SYSTEM_PROMPT,
                user_prompt=json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                response_schema=_RESPONSE_SCHEMA,
            )
        except AIError as exc:
            raise SemanticExtractionError("semantic extraction backend failed") from exc

        return self._validated_result(raw, value)

    @staticmethod
    def _validated_result(
        raw: Mapping[str, object],
        value: SemanticExtractionInput,
    ) -> SemanticLessonExtractionResult:
        if not isinstance(raw, Mapping) or set(raw) != {"proposals"}:
            raise _invalid(
                "semantic extraction response must contain exactly proposals"
            )

        raw_proposals = raw["proposals"]
        if not isinstance(raw_proposals, list):
            raise _invalid("semantic extraction proposals must be an array")

        valid_indexes = {chunk.index for chunk in value.chunks}
        proposals: list[SemanticLessonProposal] = []

        for position, raw_proposal in enumerate(raw_proposals, start=1):
            if (
                not isinstance(raw_proposal, Mapping)
                or set(raw_proposal) != _PROPOSAL_FIELDS
            ):
                raise _invalid(
                    f"semantic proposal {position} has missing or unknown fields"
                )

            title = raw_proposal["title"]
            body = raw_proposal["body"]
            rationale = raw_proposal["rationale"]
            raw_indexes = raw_proposal["supporting_chunk_indexes"]
            raw_tags = raw_proposal["tags"]
            raw_importance = raw_proposal["importance"]

            for name, item in (
                ("title", title),
                ("body", body),
                ("rationale", rationale),
            ):
                if type(item) is not str or not item.strip():
                    raise _invalid(
                        f"semantic proposal {position} {name} "
                        "must be a non-empty string"
                    )
                if any("\ud800" <= character <= "\udfff" for character in item):
                    raise _invalid(
                        f"semantic proposal {position} {name} contains invalid Unicode"
                    )

            if not isinstance(raw_indexes, list) or not raw_indexes:
                raise _invalid(f"semantic proposal {position} must cite source chunks")
            if any(type(index) is not int or index < 0 for index in raw_indexes):
                raise _invalid(
                    f"semantic proposal {position} chunk indexes "
                    "must be non-negative integers"
                )

            indexes = tuple(raw_indexes)
            if len(indexes) != len(set(indexes)):
                raise _invalid(
                    f"semantic proposal {position} chunk indexes must be unique"
                )
            if indexes != tuple(sorted(indexes)):
                raise _invalid(
                    f"semantic proposal {position} chunk indexes must be ordered"
                )
            if not set(indexes).issubset(valid_indexes):
                raise _invalid(
                    f"semantic proposal {position} references an unknown source chunk"
                )

            if not isinstance(raw_tags, list):
                raise _invalid(f"semantic proposal {position} tags must be an array")
            tags: list[str] = []
            for tag in raw_tags:
                if type(tag) is not str or not tag.strip():
                    raise _invalid(
                        f"semantic proposal {position} tags "
                        "must contain non-empty strings"
                    )
                if any("\ud800" <= character <= "\udfff" for character in tag):
                    raise _invalid(
                        f"semantic proposal {position} tag contains invalid Unicode"
                    )
                tags.append(tag)

            if raw_importance is not None and (
                type(raw_importance) is not int or not 1 <= raw_importance <= 5
            ):
                raise _invalid(
                    f"semantic proposal {position} importance "
                    "must be null or an integer from 1 through 5"
                )

            try:
                proposals.append(
                    SemanticLessonProposal(
                        title=title,
                        body=body,
                        rationale=rationale,
                        supporting_chunk_indexes=indexes,
                        topic=_optional_string(
                            raw_proposal["topic"],
                            f"semantic proposal {position} topic",
                        ),
                        tags=tuple(tags),
                        source_label=_optional_string(
                            raw_proposal["source_label"],
                            f"semantic proposal {position} source label",
                        ),
                        importance=raw_importance,
                    )
                )
            except (TypeError, ValueError) as exc:
                raise _invalid(f"semantic proposal {position} is invalid") from exc

        return SemanticLessonExtractionResult(tuple(proposals))
