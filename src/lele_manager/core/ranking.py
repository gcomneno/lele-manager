from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Literal


ArgsortKind = Literal["quicksort", "mergesort", "heapsort", "stable"]
TieBreaker = Literal["none", "lesson_id_asc"]


@dataclass(frozen=True, slots=True)
class SimilarityRankingConfig:
    """
    Configurazione ranking per LessonSimilarityIndex.

    #34: SOLO introduzione configurazione.
    Default = comportamento attuale.
    """

    # Default attuali (replicano most_similar)
    top_k_default: int = 5
    min_score_default: float = 0.0

    # None => np.argsort default (replica comportamento attuale)
    argsort_kind: ArgsortKind | None = None

    # #34: nessun tie-breaker (replica comportamento attuale)
    tiebreaker: TieBreaker = "none"


@dataclass(frozen=True, slots=True)
class RankingConfig:
    """
    Root config di ranking (prep #33 / future v2).
    """

    similarity: SimilarityRankingConfig = SimilarityRankingConfig()

    @classmethod
    def default(cls) -> "RankingConfig":
        return cls()

    def to_dict(self) -> Dict[str, Any]:
        # Serializzabile e deterministico
        return asdict(self)
