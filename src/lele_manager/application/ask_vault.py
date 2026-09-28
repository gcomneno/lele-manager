"""Application service for bounded Ask-this-Vault synthesis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from lele_manager.application.assistant_context import (
    ResolvedAssistantContext,
)
from lele_manager.core.ask_vault import (
    AskVaultCitation,
    AskVaultOutcome,
    AskVaultResult,
)


class AskVaultGroundingError(Exception):
    """A synthesizer attempted to escape the resolved canonical scope."""


class AskVaultProviderUnavailableError(Exception):
    """No Ask-this-Vault synthesis provider is configured."""


@dataclass(frozen=True, slots=True)
class AskVaultSynthesis:
    outcome: AskVaultOutcome
    answer: str
    citation_lesson_ids: tuple[str, ...]


class AskVaultSynthesizer(Protocol):
    def synthesize(
        self,
        *,
        question: str,
        context: ResolvedAssistantContext,
    ) -> AskVaultSynthesis:
        ...


class AskVaultService:
    def __init__(
        self,
        *,
        synthesizer: AskVaultSynthesizer | None,
    ) -> None:
        self._synthesizer = synthesizer

    def ask(
        self,
        *,
        question: str,
        context: ResolvedAssistantContext,
    ) -> AskVaultResult:
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("question must not be blank")

        if not context.lessons:
            return AskVaultResult(
                outcome="insufficient-support",
                answer=(
                    "The selected Vault scope does not contain "
                    "enough maintained knowledge to answer this question."
                ),
                citations=(),
            )

        if self._synthesizer is None:
            raise AskVaultProviderUnavailableError(
                "Ask-this-Vault synthesis provider is not configured."
            )

        synthesis = self._synthesizer.synthesize(
            question=normalized_question,
            context=context,
        )

        if synthesis.outcome not in {
            "answered",
            "insufficient-support",
        }:
            raise AskVaultGroundingError(
                "synthesizer returned an unsupported outcome"
            )

        allowed_ids = set(context.lesson_ids)
        citation_ids = synthesis.citation_lesson_ids

        if len(citation_ids) != len(set(citation_ids)):
            raise AskVaultGroundingError(
                "synthesizer returned duplicate citations"
            )

        outside_scope = tuple(
            lesson_id
            for lesson_id in citation_ids
            if lesson_id not in allowed_ids
        )
        if outside_scope:
            raise AskVaultGroundingError(
                "synthesizer cited lessons outside the resolved scope"
            )

        if synthesis.outcome == "answered" and not citation_ids:
            raise AskVaultGroundingError(
                "answered synthesis requires grounded citations"
            )

        answer = synthesis.answer.strip()
        if not answer:
            raise AskVaultGroundingError(
                "synthesizer returned a blank answer"
            )

        return AskVaultResult(
            outcome=synthesis.outcome,
            answer=answer,
            citations=tuple(
                AskVaultCitation(lesson_id=lesson_id)
                for lesson_id in citation_ids
            ),
        )
