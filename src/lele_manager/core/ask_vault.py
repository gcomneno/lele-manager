"""Domain contracts for grounded Ask-this-Vault answers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


AskVaultOutcome = Literal[
    "answered",
    "insufficient-support",
]


class AskVaultValidationError(ValueError):
    """Ask-this-Vault result violates the grounding contract."""


@dataclass(frozen=True, slots=True)
class AskVaultCitation:
    lesson_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.lesson_id, str) or not self.lesson_id.strip():
            raise AskVaultValidationError(
                "citation lesson_id must be a non-empty string"
            )


@dataclass(frozen=True, slots=True)
class AskVaultResult:
    outcome: AskVaultOutcome
    answer: str
    citations: tuple[AskVaultCitation, ...]

    def __post_init__(self) -> None:
        if self.outcome not in {
            "answered",
            "insufficient-support",
        }:
            raise AskVaultValidationError(
                "unsupported Ask-this-Vault outcome"
            )

        if not isinstance(self.answer, str) or not self.answer.strip():
            raise AskVaultValidationError(
                "answer must be a non-empty string"
            )

        lesson_ids = tuple(
            citation.lesson_id
            for citation in self.citations
        )

        if len(lesson_ids) != len(set(lesson_ids)):
            raise AskVaultValidationError(
                "citations must not contain duplicate lesson IDs"
            )

        if self.outcome == "answered" and not self.citations:
            raise AskVaultValidationError(
                "answered results require at least one citation"
            )
