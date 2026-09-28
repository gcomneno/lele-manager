from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from lele_manager.application.ask_vault import (
    AskVaultGroundingError,
    AskVaultProviderUnavailableError,
    AskVaultService,
    AskVaultSynthesis,
)
from lele_manager.application.assistant_context import (
    ResolvedAssistantContext,
)
from lele_manager.application.lesson_writing import (
    CanonicalLessonSnapshot,
)
from lele_manager.core.ask_vault import (
    AskVaultCitation,
    AskVaultResult,
    AskVaultValidationError,
)


def _lesson(
    lesson_id: str,
    *,
    text: str = "Maintained knowledge.",
) -> CanonicalLessonSnapshot:
    return CanonicalLessonSnapshot(
        lesson_id=lesson_id,
        title=lesson_id,
        topic=lesson_id.split("/", 1)[0],
        source="test",
        importance=3,
        tags=("ask",),
        date="2026-09-28",
        text=text,
        lifecycle="active",
        superseded_by=None,
        relationships={},
        canonical_revision="sha256:" + "a" * 64,
        relative_path=Path(f"{lesson_id}.md"),
        reviewed_at=None,
        review_interval_days=None,
    )


@dataclass
class StubSynthesizer:
    result: AskVaultSynthesis
    calls: int = 0

    def synthesize(
        self,
        *,
        question: str,
        context: ResolvedAssistantContext,
    ) -> AskVaultSynthesis:
        self.calls += 1
        assert question
        assert context.lessons
        return self.result


def test_answered_result_requires_at_least_one_citation() -> None:
    with pytest.raises(
        AskVaultValidationError,
        match="require at least one citation",
    ):
        AskVaultResult(
            outcome="answered",
            answer="Grounded answer.",
            citations=(),
        )


def test_empty_scope_returns_insufficient_support_without_provider() -> None:
    synthesizer = StubSynthesizer(
        AskVaultSynthesis(
            outcome="answered",
            answer="Should never be used.",
            citation_lesson_ids=("python/a",),
        )
    )
    service = AskVaultService(synthesizer=synthesizer)

    result = service.ask(
        question="What does the Vault say?",
        context=ResolvedAssistantContext(lessons=()),
    )

    assert result.outcome == "insufficient-support"
    assert result.citations == ()
    assert synthesizer.calls == 0


def test_answer_accepts_only_citations_from_resolved_context() -> None:
    synthesizer = StubSynthesizer(
        AskVaultSynthesis(
            outcome="answered",
            answer="Use the maintained contract.",
            citation_lesson_ids=(
                "python/a",
                "python/b",
            ),
        )
    )
    service = AskVaultService(synthesizer=synthesizer)

    result = service.ask(
        question="What should I use?",
        context=ResolvedAssistantContext(
            lessons=(
                _lesson("python/a"),
                _lesson("python/b"),
            )
        ),
    )

    assert result.outcome == "answered"
    assert result.answer == "Use the maintained contract."
    assert result.citations == (
        AskVaultCitation("python/a"),
        AskVaultCitation("python/b"),
    )


def test_provider_cannot_invent_citation_outside_resolved_scope() -> None:
    service = AskVaultService(
        synthesizer=StubSynthesizer(
            AskVaultSynthesis(
                outcome="answered",
                answer="Invented grounding.",
                citation_lesson_ids=("python/not-in-scope",),
            )
        )
    )

    with pytest.raises(
        AskVaultGroundingError,
        match="outside the resolved scope",
    ):
        service.ask(
            question="Question?",
            context=ResolvedAssistantContext(
                lessons=(_lesson("python/current"),)
            ),
        )


def test_provider_cannot_claim_answer_without_grounding() -> None:
    service = AskVaultService(
        synthesizer=StubSynthesizer(
            AskVaultSynthesis(
                outcome="answered",
                answer="Unsupported answer.",
                citation_lesson_ids=(),
            )
        )
    )

    with pytest.raises(
        AskVaultGroundingError,
        match="requires grounded citations",
    ):
        service.ask(
            question="Question?",
            context=ResolvedAssistantContext(
                lessons=(_lesson("python/current"),)
            ),
        )


def test_insufficient_support_is_explicit_and_may_have_no_citations() -> None:
    service = AskVaultService(
        synthesizer=StubSynthesizer(
            AskVaultSynthesis(
                outcome="insufficient-support",
                answer=(
                    "The maintained LeLe do not contain enough "
                    "information to answer."
                ),
                citation_lesson_ids=(),
            )
        )
    )

    result = service.ask(
        question="Unknown detail?",
        context=ResolvedAssistantContext(
            lessons=(_lesson("python/current"),)
        ),
    )

    assert result.outcome == "insufficient-support"
    assert result.citations == ()


def test_duplicate_provider_citations_fail_closed() -> None:
    service = AskVaultService(
        synthesizer=StubSynthesizer(
            AskVaultSynthesis(
                outcome="answered",
                answer="Grounded.",
                citation_lesson_ids=(
                    "python/current",
                    "python/current",
                ),
            )
        )
    )

    with pytest.raises(
        AskVaultGroundingError,
        match="duplicate citations",
    ):
        service.ask(
            question="Question?",
            context=ResolvedAssistantContext(
                lessons=(_lesson("python/current"),)
            ),
        )


def test_blank_question_is_rejected_before_provider() -> None:
    synthesizer = StubSynthesizer(
        AskVaultSynthesis(
            outcome="answered",
            answer="Unused.",
            citation_lesson_ids=("python/current",),
        )
    )
    service = AskVaultService(synthesizer=synthesizer)

    with pytest.raises(ValueError, match="question must not be blank"):
        service.ask(
            question="   ",
            context=ResolvedAssistantContext(
                lessons=(_lesson("python/current"),)
            ),
        )

    assert synthesizer.calls == 0


def test_non_empty_scope_without_provider_fails_closed() -> None:
    service = AskVaultService(synthesizer=None)

    with pytest.raises(
        AskVaultProviderUnavailableError,
        match="provider is not configured",
    ):
        service.ask(
            question="Question?",
            context=ResolvedAssistantContext(
                lessons=(_lesson("python/current"),)
            ),
        )
